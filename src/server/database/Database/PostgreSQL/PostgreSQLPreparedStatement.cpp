/*
 * This file is part of the TrinityCore Project. See AUTHORS file for Copyright information
 *
 * This program is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by the
 * Free Software Foundation; either version 2 of the License, or (at your
 * option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
 * more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program. If not, see <http://www.gnu.org/licenses/>.
 */

#include "PostgreSQLPreparedStatement.h"
#include "Errors.h"
#include "Log.h"
#include "PreparedStatement.h"
#include <atomic>
#include <cstring>
#include <sstream>
#include <type_traits>

PostgreSQLPreparedStatement::PostgreSQLPreparedStatement(std::string_view queryString, PGconn* conn)
    : m_stmt(nullptr)
    , m_conn(conn)
    , m_paramCount(0)
    , m_queryString(queryString)
{
    // Generate unique statement name using atomic counter
    static std::atomic<uint32> stmtCounter{0};
    m_stmtName = "stmt_" + std::to_string(++stmtCounter);

    // Convert MySQL-style ? placeholders to PostgreSQL $1, $2, etc.
    std::string convertedQuery;
    convertedQuery.reserve(m_queryString.size());
    uint32 paramIndex = 0;
    bool inString = false;
    char stringDelimiter = '\0';

    for (size_t i = 0; i < m_queryString.length(); ++i)
    {
        char c = m_queryString[i];

        if (!inString && (c == '\'' || c == '"'))
        {
            inString = true;
            stringDelimiter = c;
            convertedQuery += c;
        }
        else if (inString && c == stringDelimiter)
        {
            if (i + 1 < m_queryString.length() && m_queryString[i + 1] == stringDelimiter)
            {
                convertedQuery += c;
                convertedQuery += m_queryString[++i];
            }
            else
            {
                inString = false;
                convertedQuery += c;
            }
        }
        else if (!inString && c == '?')
        {
            convertedQuery += '$';
            convertedQuery += std::to_string(++paramIndex);
        }
        else
        {
            convertedQuery += c;
        }
    }

    m_paramCount = paramIndex;
    m_queryString = std::move(convertedQuery);

    PGresult* result = PQprepare(m_conn, m_stmtName.c_str(), m_queryString.c_str(), m_paramCount, nullptr);
    if (PQresultStatus(result) != PGRES_COMMAND_OK)
    {
        TC_LOG_ERROR("sql.sql", "Failed to prepare statement '{}': {}\nQuery: {}",
                     m_stmtName, PQerrorMessage(m_conn), m_queryString);
        PQclear(result);
        m_stmtName.clear(); // Signal failure
        return;
    }
    PQclear(result);

    if (m_paramCount > 0)
    {
        m_paramsSet.resize(m_paramCount, false);
        m_paramValues.resize(m_paramCount, nullptr);
        m_paramLengths.resize(m_paramCount, 0);
        m_paramFormats.resize(m_paramCount, 0);
        m_paramStringStorage.resize(m_paramCount);
    }
}

PostgreSQLPreparedStatement::~PostgreSQLPreparedStatement()
{
    ClearParameters();

    if (m_conn && !m_stmtName.empty())
    {
        std::string deallocQuery = "DEALLOCATE " + m_stmtName;
        PGresult* result = PQexec(m_conn, deallocQuery.c_str());
        if (result)
            PQclear(result);
    }
}

void PostgreSQLPreparedStatement::BindParameters(PreparedStatementBase* stmt)
{
    m_stmt = stmt;
    ClearParameters();

    uint8 pos = 0;
    auto const& params = stmt->GetParameters();
    for (auto const& data : params)
    {
        std::visit([this, &pos](auto&& arg) {
            using T = std::decay_t<decltype(arg)>;
            if constexpr (std::is_same_v<T, std::nullptr_t>)
                SetParameter(pos++, nullptr);
            else if constexpr (std::is_same_v<T, bool>)
                SetParameter(pos++, arg);
            else if constexpr (std::is_same_v<T, uint8>)
                SetParameter(pos++, arg);
            else if constexpr (std::is_same_v<T, uint16>)
                SetParameter(pos++, arg);
            else if constexpr (std::is_same_v<T, uint32>)
                SetParameter(pos++, arg);
            else if constexpr (std::is_same_v<T, uint64>)
                SetParameter(pos++, arg);
            else if constexpr (std::is_same_v<T, int8>)
                SetParameter(pos++, arg);
            else if constexpr (std::is_same_v<T, int16>)
                SetParameter(pos++, arg);
            else if constexpr (std::is_same_v<T, int32>)
                SetParameter(pos++, arg);
            else if constexpr (std::is_same_v<T, int64>)
                SetParameter(pos++, arg);
            else if constexpr (std::is_same_v<T, float>)
                SetParameter(pos++, arg);
            else if constexpr (std::is_same_v<T, double>)
                SetParameter(pos++, arg);
            else if constexpr (std::is_same_v<T, std::string>)
                SetParameter(pos++, arg);
            else if constexpr (std::is_same_v<T, std::vector<uint8>>)
                SetParameter(pos++, arg);
            else if constexpr (std::is_same_v<T, SystemTimePoint>)
                SetParameter(pos++, arg);
        }, data.data);
    }
}

void PostgreSQLPreparedStatement::SetParameter(uint8 index, std::nullptr_t)
{
    AssertValidIndex(index);
    m_paramValues[index] = nullptr;
    m_paramLengths[index] = 0;
    m_paramFormats[index] = 0;
    m_paramsSet[index] = true;
}

void PostgreSQLPreparedStatement::SetParameter(uint8 index, bool value)
{
    SetParameter(index, value ? uint8(1) : uint8(0));
}

template<typename T>
void PostgreSQLPreparedStatement::SetParameter(uint8 index, T value)
{
    AssertValidIndex(index);

    std::stringstream ss;
    if constexpr (std::is_same_v<T, uint8>)
        ss << static_cast<uint32>(value);
    else if constexpr (std::is_same_v<T, int8>)
        ss << static_cast<int32>(value);
    else
        ss << value;
    m_paramStringStorage[index] = ss.str();
    m_paramValues[index] = m_paramStringStorage[index].c_str();
    m_paramLengths[index] = m_paramStringStorage[index].length();
    m_paramFormats[index] = 0; // text format
    m_paramsSet[index] = true;
}

void PostgreSQLPreparedStatement::SetParameter(uint8 index, SystemTimePoint value)
{
    SetParameter(index, std::chrono::system_clock::to_time_t(value));
}

void PostgreSQLPreparedStatement::SetParameter(uint8 index, std::string const& value)
{
    AssertValidIndex(index);

    m_paramStringStorage[index] = value;
    m_paramValues[index] = m_paramStringStorage[index].c_str();
    m_paramLengths[index] = m_paramStringStorage[index].length();
    m_paramFormats[index] = 0; // text format
    m_paramsSet[index] = true;
}

void PostgreSQLPreparedStatement::SetParameter(uint8 index, std::vector<uint8> const& value)
{
    AssertValidIndex(index);

    if (value.empty())
    {
        SetParameter(index, nullptr);
        return;
    }

    // Binary format for bytea
    m_paramStringStorage[index].assign(reinterpret_cast<const char*>(value.data()), value.size());
    m_paramValues[index] = m_paramStringStorage[index].data();
    m_paramLengths[index] = value.size();
    m_paramFormats[index] = 1; // binary format
    m_paramsSet[index] = true;
}

void PostgreSQLPreparedStatement::ClearParameters()
{
    for (uint32 i = 0; i < m_paramCount; ++i)
    {
        m_paramValues[i] = nullptr;
        m_paramLengths[i] = 0;
        m_paramFormats[i] = 0;
        m_paramStringStorage[i].clear();
        m_paramsSet[i] = false;
    }
}

void PostgreSQLPreparedStatement::AssertValidIndex(uint8 index)
{
    ASSERT(index < m_paramCount, "Parameter index %u out of range (max: %u) for statement: %s",
           uint32(index), m_paramCount, m_queryString.c_str());
}

std::string PostgreSQLPreparedStatement::getQueryString() const
{
    return m_queryString;
}

// Explicit template instantiations
template void PostgreSQLPreparedStatement::SetParameter(uint8 index, uint8 value);
template void PostgreSQLPreparedStatement::SetParameter(uint8 index, int8 value);
template void PostgreSQLPreparedStatement::SetParameter(uint8 index, uint16 value);
template void PostgreSQLPreparedStatement::SetParameter(uint8 index, int16 value);
template void PostgreSQLPreparedStatement::SetParameter(uint8 index, uint32 value);
template void PostgreSQLPreparedStatement::SetParameter(uint8 index, int32 value);
template void PostgreSQLPreparedStatement::SetParameter(uint8 index, uint64 value);
template void PostgreSQLPreparedStatement::SetParameter(uint8 index, int64 value);
template void PostgreSQLPreparedStatement::SetParameter(uint8 index, float value);
template void PostgreSQLPreparedStatement::SetParameter(uint8 index, double value);
