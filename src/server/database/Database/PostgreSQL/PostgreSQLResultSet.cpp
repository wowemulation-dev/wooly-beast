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

#include "PostgreSQLResultSet.h"
#include "Errors.h"
#include "FieldValueConverters.h"
#include "Log.h"
#include <cstring>
#include <libpq-fe.h>

namespace
{
// PostgreSQL OID constants for built-in types
constexpr unsigned int BOOLOID = 16;
constexpr unsigned int INT2OID = 21;
constexpr unsigned int INT4OID = 23;
constexpr unsigned int INT8OID = 20;
constexpr unsigned int OIDOID = 26;
constexpr unsigned int FLOAT4OID = 700;
constexpr unsigned int FLOAT8OID = 701;
constexpr unsigned int NUMERICOID = 1700;
constexpr unsigned int TEXTOID = 25;
constexpr unsigned int VARCHAROID = 1043;
constexpr unsigned int BPCHAROID = 1042;
constexpr unsigned int NAMEOID = 19;
constexpr unsigned int BYTEAOID = 17;
constexpr unsigned int TIMESTAMPOID = 1114;
constexpr unsigned int TIMESTAMPTZOID = 1184;
constexpr unsigned int DATEOID = 1082;
constexpr unsigned int TIMEOID = 1083;
constexpr unsigned int TIMETZOID = 1266;

DatabaseFieldTypes ConvertPostgreSQLType(unsigned int pgsqlType)
{
    switch (pgsqlType)
    {
        case BOOLOID:          return DatabaseFieldTypes::UInt8;
        case INT2OID:          return DatabaseFieldTypes::Int16;
        case INT4OID:          return DatabaseFieldTypes::Int32;
        case INT8OID:          return DatabaseFieldTypes::Int64;
        case OIDOID:           return DatabaseFieldTypes::UInt32;
        case FLOAT4OID:        return DatabaseFieldTypes::Float;
        case FLOAT8OID:        return DatabaseFieldTypes::Double;
        case NUMERICOID:       return DatabaseFieldTypes::Decimal;
        case TEXTOID:
        case VARCHAROID:
        case BPCHAROID:
        case NAMEOID:          return DatabaseFieldTypes::Binary;
        case BYTEAOID:         return DatabaseFieldTypes::Binary;
        case TIMESTAMPOID:
        case TIMESTAMPTZOID:   return DatabaseFieldTypes::Date;
        case DATEOID:          return DatabaseFieldTypes::Date;
        case TIMEOID:
        case TIMETZOID:        return DatabaseFieldTypes::Time;
        default:
            TC_LOG_WARN("sql.sql", "Unknown PostgreSQL type OID {}, treating as string", pgsqlType);
            return DatabaseFieldTypes::Binary;
    }
}

char const* PostgreSQLTypeToString(unsigned int pgsqlType)
{
    switch (pgsqlType)
    {
        case BOOLOID:        return "BOOL";
        case INT2OID:        return "INT2";
        case INT4OID:        return "INT4";
        case INT8OID:        return "INT8";
        case OIDOID:         return "OID";
        case FLOAT4OID:      return "FLOAT4";
        case FLOAT8OID:      return "FLOAT8";
        case NUMERICOID:     return "NUMERIC";
        case TEXTOID:        return "TEXT";
        case VARCHAROID:     return "VARCHAR";
        case BPCHAROID:      return "BPCHAR";
        case NAMEOID:        return "NAME";
        case BYTEAOID:       return "BYTEA";
        case TIMESTAMPOID:   return "TIMESTAMP";
        case TIMESTAMPTZOID: return "TIMESTAMPTZ";
        case DATEOID:        return "DATE";
        case TIMEOID:        return "TIME";
        case TIMETZOID:      return "TIMETZ";
        default:             return "UNKNOWN";
    }
}

// PostgreSQL text-format value converters.
// PostgreSQL returns all values as text (format 0), so we always use
// FromStringToDatabaseTypeConverter for numeric types.
std::unique_ptr<BaseDatabaseResultValueConverter> const PostgreSQLValueConverters[15] =
{
    nullptr,                                                                                         // Null
    std::make_unique<PrimitiveResultValueConverter<uint8, FromStringToDatabaseTypeConverter>>(),      // UInt8
    std::make_unique<PrimitiveResultValueConverter<int8, FromStringToDatabaseTypeConverter>>(),       // Int8
    std::make_unique<PrimitiveResultValueConverter<uint16, FromStringToDatabaseTypeConverter>>(),     // UInt16
    std::make_unique<PrimitiveResultValueConverter<int16, FromStringToDatabaseTypeConverter>>(),      // Int16
    std::make_unique<PrimitiveResultValueConverter<uint32, FromStringToDatabaseTypeConverter>>(),     // UInt32
    std::make_unique<PrimitiveResultValueConverter<int32, FromStringToDatabaseTypeConverter>>(),      // Int32
    std::make_unique<PrimitiveResultValueConverter<uint64, FromStringToDatabaseTypeConverter>>(),     // UInt64
    std::make_unique<PrimitiveResultValueConverter<int64, FromStringToDatabaseTypeConverter>>(),      // Int64
    std::make_unique<PrimitiveResultValueConverter<float, FromStringToDatabaseTypeConverter>>(),      // Float
    std::make_unique<PrimitiveResultValueConverter<double, FromStringToDatabaseTypeConverter>>(),     // Double
    std::make_unique<PrimitiveResultValueConverter<double, FromStringToDatabaseTypeConverter>>(),     // Decimal
    std::make_unique<StringResultValueConverter>(),                                                   // Date (returned as text string)
    std::make_unique<StringResultValueConverter>(),                                                   // Time (returned as text string)
    std::make_unique<StringResultValueConverter>()                                                    // Binary (string/bytea)
};

void DecodeByteaHex(char const* data, uint32 textLen, std::vector<uint8>& outBuffer)
{
    // PostgreSQL returns bytea in hex format: \x followed by hex digits
    if (textLen < 2 || data[0] != '\\' || data[1] != 'x')
    {
        outBuffer.assign(data, data + textLen);
        return;
    }

    data += 2;
    textLen -= 2;

    uint32 binaryLen = textLen / 2;
    outBuffer.resize(binaryLen);

    auto hexVal = [](char c) -> uint8 {
        if (c >= '0' && c <= '9') return c - '0';
        if (c >= 'a' && c <= 'f') return c - 'a' + 10;
        if (c >= 'A' && c <= 'F') return c - 'A' + 10;
        return 0;
    };

    for (uint32 i = 0; i < binaryLen; ++i)
        outBuffer[i] = (hexVal(data[i * 2]) << 4) | hexVal(data[i * 2 + 1]);
}
}

// ---- ResultSet ----

ResultSet::ResultSet(PGresult* result, uint64 rowCount, uint32 fieldCount) :
_rowCount(rowCount),
_currentRow(nullptr),
_fieldCount(fieldCount),
_result(result),
_currentRowIndex(-1)
{
    if (!_result)
        return;

    _rowCount = PQntuples(_result);
    _fieldCount = PQnfields(_result);

    if (_fieldCount > 0)
    {
        _currentRow = new Field[_fieldCount];
        _fieldMetadata.resize(_fieldCount);
        _fieldIndexByAlias.reserve(_fieldCount);
        _columnNames.resize(_fieldCount);
        _fieldOids.resize(_fieldCount);
        _byteaBuffers.resize(_fieldCount);

        for (uint32 i = 0; i < _fieldCount; ++i)
        {
            unsigned int oid = PQftype(_result, i);
            _fieldOids[i] = oid;
            _columnNames[i] = PQfname(_result, i);

            _fieldMetadata[i].TableName = "";
            _fieldMetadata[i].TableAlias = "";
            _fieldMetadata[i].Name = _columnNames[i].c_str();
            _fieldMetadata[i].Alias = _columnNames[i].c_str();
            _fieldMetadata[i].TypeName = PostgreSQLTypeToString(oid);
            _fieldMetadata[i].Index = i;
            _fieldMetadata[i].Type = ConvertPostgreSQLType(oid);
            _fieldMetadata[i].Converter = PostgreSQLValueConverters[AsUnderlyingType(_fieldMetadata[i].Type)].get();

            auto [itr, success] = _fieldIndexByAlias.try_emplace(
                { Trinity::DB::FieldLookupByAliasKey::RuntimeInit, _columnNames[i] }, i);
            ASSERT(success, "Duplicate column alias %s in query at index %u and %zu",
                _columnNames[i].c_str(), i, itr->second);

            _currentRow[i].SetMetadata(&_fieldMetadata[i]);
        }
    }
}

ResultSet::~ResultSet()
{
    CleanUp();
}

bool ResultSet::NextRow()
{
    if (!_result)
        return false;

    if (++_currentRowIndex >= static_cast<int>(_rowCount))
    {
        CleanUp();
        return false;
    }

    for (uint32 i = 0; i < _fieldCount; ++i)
    {
        if (PQgetisnull(_result, _currentRowIndex, i))
        {
            _currentRow[i].SetValue(nullptr, 0);
        }
        else
        {
            char* value = PQgetvalue(_result, _currentRowIndex, i);
            int length = PQgetlength(_result, _currentRowIndex, i);

            if (_fieldOids[i] == BYTEAOID && length > 0)
            {
                DecodeByteaHex(value, length, _byteaBuffers[i]);
                _currentRow[i].SetValue(
                    reinterpret_cast<char const*>(_byteaBuffers[i].data()),
                    static_cast<uint32>(_byteaBuffers[i].size()));
            }
            else
            {
                _currentRow[i].SetValue(value, length);
            }
        }
    }

    return true;
}

Field const& ResultSet::operator[](std::size_t index) const
{
    ASSERT(index < std::size_t(_fieldCount));
    return _currentRow[index];
}

Field const& ResultSet::operator[](Trinity::DB::FieldLookupByAliasKey const& alias) const
{
    auto itr = _fieldIndexByAlias.find(alias);
    ASSERT(itr != _fieldIndexByAlias.end());
    return _currentRow[itr->second];
}

QueryResultFieldMetadata const& ResultSet::GetFieldMetadata(std::size_t index) const
{
    ASSERT(index < std::size_t(_fieldCount));
    return _fieldMetadata[index];
}

QueryResultFieldMetadata const& ResultSet::GetFieldMetadata(Trinity::DB::FieldLookupByAliasKey const& alias) const
{
    auto itr = _fieldIndexByAlias.find(alias);
    ASSERT(itr != _fieldIndexByAlias.end());
    return _fieldMetadata[itr->second];
}

void ResultSet::CleanUp()
{
    if (_currentRow)
    {
        delete [] _currentRow;
        _currentRow = nullptr;
    }

    if (_result)
    {
        PQclear(_result);
        _result = nullptr;
    }
}

// ---- PreparedResultSet ----

PreparedResultSet::PreparedResultSet(PGresult* result, uint64 rowCount, uint32 fieldCount) :
m_rowCount(rowCount),
m_rowPosition(0),
m_fieldCount(fieldCount),
m_result(result)
{
    if (!m_result)
        return;

    m_rowCount = PQntuples(m_result);
    m_fieldCount = PQnfields(m_result);

    if (m_fieldCount > 0)
    {
        m_fieldMetadata.resize(m_fieldCount);
        m_fieldIndexByAlias.reserve(m_fieldCount);
        m_columnNames.resize(m_fieldCount);
        m_fieldOids.resize(m_fieldCount);

        for (uint32 i = 0; i < m_fieldCount; ++i)
        {
            unsigned int oid = PQftype(m_result, i);
            m_fieldOids[i] = oid;
            m_columnNames[i] = PQfname(m_result, i);

            m_fieldMetadata[i].TableName = "";
            m_fieldMetadata[i].TableAlias = "";
            m_fieldMetadata[i].Name = m_columnNames[i].c_str();
            m_fieldMetadata[i].Alias = m_columnNames[i].c_str();
            m_fieldMetadata[i].TypeName = PostgreSQLTypeToString(oid);
            m_fieldMetadata[i].Index = i;
            m_fieldMetadata[i].Type = ConvertPostgreSQLType(oid);
            m_fieldMetadata[i].Converter = PostgreSQLValueConverters[AsUnderlyingType(m_fieldMetadata[i].Type)].get();

            auto [itr, success] = m_fieldIndexByAlias.try_emplace(
                { Trinity::DB::FieldLookupByAliasKey::RuntimeInit, m_columnNames[i] }, i);
            ASSERT(success, "Duplicate column alias %s in query at index %u and %zu",
                m_columnNames[i].c_str(), i, itr->second);
        }

        // Buffer all rows upfront, matching MySQL PreparedResultSet behavior.
        // The usage pattern is: do { Fetch(); } while (NextRow());
        m_rows.resize(std::size_t(m_rowCount) * m_fieldCount);
        m_byteaBuffers.resize(std::size_t(m_rowCount) * m_fieldCount);

        for (uint64 row = 0; row < m_rowCount; ++row)
        {
            for (uint32 col = 0; col < m_fieldCount; ++col)
            {
                std::size_t idx = std::size_t(row) * m_fieldCount + col;
                m_rows[idx].SetMetadata(&m_fieldMetadata[col]);

                if (PQgetisnull(m_result, static_cast<int>(row), col))
                {
                    m_rows[idx].SetValue(nullptr, 0);
                }
                else
                {
                    char* value = PQgetvalue(m_result, static_cast<int>(row), col);
                    int length = PQgetlength(m_result, static_cast<int>(row), col);

                    if (m_fieldOids[col] == BYTEAOID && length > 0)
                    {
                        DecodeByteaHex(value, length, m_byteaBuffers[idx]);
                        m_rows[idx].SetValue(
                            reinterpret_cast<char const*>(m_byteaBuffers[idx].data()),
                            static_cast<uint32>(m_byteaBuffers[idx].size()));
                    }
                    else
                    {
                        m_rows[idx].SetValue(value, length);
                    }
                }
            }
        }
    }
}

PreparedResultSet::~PreparedResultSet()
{
    CleanUp();
}

bool PreparedResultSet::NextRow()
{
    if (++m_rowPosition >= m_rowCount)
        return false;

    return true;
}

Field* PreparedResultSet::Fetch() const
{
    ASSERT(m_rowPosition < m_rowCount);
    return const_cast<Field*>(&m_rows[std::size_t(m_rowPosition) * m_fieldCount]);
}

Field const& PreparedResultSet::operator[](std::size_t index) const
{
    ASSERT(m_rowPosition < m_rowCount);
    ASSERT(index < std::size_t(m_fieldCount));
    return m_rows[std::size_t(m_rowPosition) * m_fieldCount + index];
}

Field const& PreparedResultSet::operator[](Trinity::DB::FieldLookupByAliasKey const& alias) const
{
    ASSERT(m_rowPosition < m_rowCount);
    auto itr = m_fieldIndexByAlias.find(alias);
    ASSERT(itr != m_fieldIndexByAlias.end());
    return m_rows[std::size_t(m_rowPosition) * m_fieldCount + itr->second];
}

QueryResultFieldMetadata const& PreparedResultSet::GetFieldMetadata(std::size_t index) const
{
    ASSERT(index < std::size_t(m_fieldCount));
    return m_fieldMetadata[index];
}

QueryResultFieldMetadata const& PreparedResultSet::GetFieldMetadata(Trinity::DB::FieldLookupByAliasKey const& alias) const
{
    auto itr = m_fieldIndexByAlias.find(alias);
    ASSERT(itr != m_fieldIndexByAlias.end());
    return m_fieldMetadata[itr->second];
}

void PreparedResultSet::CleanUp()
{
    if (m_result)
    {
        PQclear(m_result);
        m_result = nullptr;
    }
}
