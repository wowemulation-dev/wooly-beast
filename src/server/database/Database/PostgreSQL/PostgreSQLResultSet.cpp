/**
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors
 */

#include "PostgreSQLResultSet.h"
#include "Log.h"
#include "Util.h"
#include "FieldValueConverters.h"
#include <cstring>
#include <libpq-fe.h>

// Define the value converters for PostgreSQL (text format)
// This matches the definition in QueryResult.cpp but is needed here for PostgreSQL builds
namespace
{
    // Converter template for string-to-type conversion
    template<typename T>
    struct FromStringToDatabaseTypeConverter
    {
        static T GetDatabaseValue(char const* data, uint32 size)
        {
            return Trinity::StringTo<T>(std::string_view(data, size)).value_or(T{});
        }

        static char const* GetStringValue(char const* data)
        {
            return data;
        }
    };

    // Specialization for string types
    template<>
    struct FromStringToDatabaseTypeConverter<char const*>
    {
        static char const* GetDatabaseValue(char const* data, uint32 /*size*/)
        {
            return data;
        }

        static char const* GetStringValue(char const* data)
        {
            return data;
        }
    };

    std::unique_ptr<BaseDatabaseResultValueConverter> const PostgreSQLStringConverters[15] =
    {
        nullptr,
        std::make_unique<PrimitiveResultValueConverter<uint8, FromStringToDatabaseTypeConverter>>(),
        std::make_unique<PrimitiveResultValueConverter<int8, FromStringToDatabaseTypeConverter>>(),
        std::make_unique<PrimitiveResultValueConverter<uint16, FromStringToDatabaseTypeConverter>>(),
        std::make_unique<PrimitiveResultValueConverter<int16, FromStringToDatabaseTypeConverter>>(),
        std::make_unique<PrimitiveResultValueConverter<uint32, FromStringToDatabaseTypeConverter>>(),
        std::make_unique<PrimitiveResultValueConverter<int32, FromStringToDatabaseTypeConverter>>(),
        std::make_unique<PrimitiveResultValueConverter<uint64, FromStringToDatabaseTypeConverter>>(),
        std::make_unique<PrimitiveResultValueConverter<int64, FromStringToDatabaseTypeConverter>>(),
        std::make_unique<PrimitiveResultValueConverter<float, FromStringToDatabaseTypeConverter>>(),
        std::make_unique<PrimitiveResultValueConverter<double, FromStringToDatabaseTypeConverter>>(),
        std::make_unique<PrimitiveResultValueConverter<double, FromStringToDatabaseTypeConverter>>(), // Decimal
        std::make_unique<NotImplementedResultValueConverter>(), // Date - TODO: Implement proper date converter
        std::make_unique<NotImplementedResultValueConverter>(), // Time - TODO: Implement proper time converter
        std::make_unique<StringResultValueConverter>() // Binary
    };

    // Decode PostgreSQL bytea hex format to raw binary
    // PostgreSQL returns bytea as text in hex format: \x followed by hex digits
    // e.g., \x8d173cc381961eebabf336f5e6675b101bb513e5 (42 chars for 20 bytes)
    void DecodeByteaHex(char const* data, uint32 textLen, std::vector<uint8>& outBuffer)
    {
        // Check for hex format prefix
        if (textLen < 2 || data[0] != '\\' || data[1] != 'x')
        {
            // Not hex format - copy as-is
            outBuffer.assign(data, data + textLen);
            return;
        }

        // Skip the \x prefix
        data += 2;
        textLen -= 2;

        // Each pair of hex chars = 1 byte
        uint32 binaryLen = textLen / 2;
        outBuffer.resize(binaryLen);

        auto hexVal = [](char c) -> uint8 {
            if (c >= '0' && c <= '9') return c - '0';
            if (c >= 'a' && c <= 'f') return c - 'a' + 10;
            if (c >= 'A' && c <= 'F') return c - 'A' + 10;
            return 0;
        };

        for (uint32 i = 0; i < binaryLen; ++i)
        {
            char high = data[i * 2];
            char low = data[i * 2 + 1];
            outBuffer[i] = (hexVal(high) << 4) | hexVal(low);
        }
    }

    // PostgreSQL OID constants for built-in types
    // These are stable across PostgreSQL versions
    // See: https://www.postgresql.org/docs/current/catalog-pg-type.html
    constexpr Oid BOOLOID = 16;
    constexpr Oid INT2OID = 21;
    constexpr Oid INT4OID = 23;
    constexpr Oid INT8OID = 20;
    constexpr Oid OIDOID = 26;
    constexpr Oid FLOAT4OID = 700;
    constexpr Oid FLOAT8OID = 701;
    constexpr Oid NUMERICOID = 1700;
    constexpr Oid TEXTOID = 25;
    constexpr Oid VARCHAROID = 1043;
    constexpr Oid BPCHAROID = 1042;
    constexpr Oid NAMEOID = 19;
    constexpr Oid BYTEAOID = 17;
    constexpr Oid TIMESTAMPOID = 1114;
    constexpr Oid TIMESTAMPTZOID = 1184;
    constexpr Oid DATEOID = 1082;
    constexpr Oid TIMEOID = 1083;
    constexpr Oid TIMETZOID = 1266;

    DatabaseFieldTypes ConvertPostgreSQLType(Oid pgsqlType)
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
            case TIMESTAMPTZOID:
            case DATEOID:
            case TIMEOID:
            case TIMETZOID:        return DatabaseFieldTypes::Date;
            default:
                TC_LOG_WARN("sql.sql", "Unknown PostgreSQL type OID {}, treating as string", pgsqlType);
                return DatabaseFieldTypes::Binary;
        }
    }
}

// ResultSet implementation
ResultSet::ResultSet(PGresult* result, uint64 rowCount, uint32 fieldCount)
    : m_rowCount(rowCount)
    , m_currentRowData(nullptr)
    , m_fieldCount(fieldCount)
    , m_result(result)
    , m_currentRowIndex(-1)
{
    if (!m_result)
        return;

    // Check result status
    ExecStatusType status = PQresultStatus(m_result);
    if (status != PGRES_TUPLES_OK && status != PGRES_SINGLE_TUPLE)
    {
        TC_LOG_ERROR("sql.sql", "PostgreSQL query result error: {}", PQresultErrorMessage(m_result));
        CleanUp();
        return;
    }

    // Get actual counts from result
    m_rowCount = PQntuples(m_result);
    m_fieldCount = PQnfields(m_result);

    if (m_fieldCount > 0)
    {
        m_fields = std::make_unique<Field[]>(m_fieldCount);
        m_currentRowData = m_fields.get();
        _fieldMetadata.resize(m_fieldCount);
        m_fieldOids.resize(m_fieldCount);
        m_byteaBuffers.resize(m_fieldCount);

        // Set field types and metadata based on PostgreSQL column types
        for (uint32 i = 0; i < m_fieldCount; ++i)
        {
            Oid fieldType = PQftype(m_result, i);
            m_fieldOids[i] = fieldType;

            // Populate field metadata
            _fieldMetadata[i].TableName = "";  // PostgreSQL doesn't provide table name in results
            _fieldMetadata[i].TableAlias = "";
            _fieldMetadata[i].Name = PQfname(m_result, i);
            _fieldMetadata[i].Alias = PQfname(m_result, i);
            _fieldMetadata[i].TypeName = "";
            _fieldMetadata[i].Index = i;
            _fieldMetadata[i].Type = ConvertPostgreSQLType(fieldType);

            // PostgreSQL always returns text format, so use string converters
            _fieldMetadata[i].Converter = PostgreSQLStringConverters[AsUnderlyingType(_fieldMetadata[i].Type)].get();

            // Set metadata for the field
            m_fields[i].SetMetadata(&_fieldMetadata[i]);
        }

        // Note: Unlike PreparedResultSet, we do NOT pre-fetch here.
        // DatabaseWorkerPool::Query() calls NextRow() as part of its validation,
        // which serves as the initial row fetch. This matches MySQL's behavior
        // where mysql_fetch_row() is first called in NextRow(), not in the constructor.
    }
}

ResultSet::~ResultSet()
{
    CleanUp();
}

bool ResultSet::NextRow()
{
    if (!m_result)
        return false;

    if (++m_currentRowIndex >= static_cast<int>(m_rowCount))
        return false;

    // Update field values for current row
    for (uint32 i = 0; i < m_fieldCount; ++i)
    {
        if (PQgetisnull(m_result, m_currentRowIndex, i))
        {
            m_fields[i].SetValue(nullptr, 0);
        }
        else
        {
            char* value = PQgetvalue(m_result, m_currentRowIndex, i);
            int length = PQgetlength(m_result, m_currentRowIndex, i);

            // Decode bytea columns from hex format to raw binary
            if (m_fieldOids[i] == BYTEAOID && length > 0)
            {
                DecodeByteaHex(value, length, m_byteaBuffers[i]);
                m_fields[i].SetValue(reinterpret_cast<char const*>(m_byteaBuffers[i].data()),
                                     static_cast<uint32>(m_byteaBuffers[i].size()));
            }
            else
            {
                m_fields[i].SetValue(value, length);
            }
        }
    }

    return true;
}

Field const& ResultSet::operator[](std::size_t index) const
{
    ASSERT(index < m_fieldCount);
    return m_fields[index];
}

QueryResultFieldMetadata const& ResultSet::GetFieldMetadata(std::size_t index) const
{
    ASSERT(index < m_fieldCount);
    return _fieldMetadata[index];
}

void ResultSet::CleanUp()
{
    if (m_result)
    {
        PQclear(m_result);
        m_result = nullptr;
    }
    m_currentRowData = nullptr;
}

// PreparedResultSet implementation
PreparedResultSet::PreparedResultSet(PGresult* result, uint64 rowCount, uint32 fieldCount)
    : m_rowCount(rowCount)
    , m_currentRowData(nullptr)
    , m_fieldCount(fieldCount)
    , m_result(result)
    , m_currentRowIndex(-1)
{
    if (!m_result)
        return;

    // Check result status
    ExecStatusType status = PQresultStatus(m_result);
    if (status != PGRES_TUPLES_OK && status != PGRES_SINGLE_TUPLE)
    {
        TC_LOG_ERROR("sql.sql", "PostgreSQL prepared query result error: {}", PQresultErrorMessage(m_result));
        CleanUp();
        return;
    }

    // Get actual counts from result
    m_rowCount = PQntuples(m_result);
    m_fieldCount = PQnfields(m_result);

    if (m_fieldCount > 0)
    {
        m_fields = std::make_unique<Field[]>(m_fieldCount);
        m_currentRowData = m_fields.get();
        m_fieldMetadata.resize(m_fieldCount);
        m_fieldOids.resize(m_fieldCount);
        m_byteaBuffers.resize(m_fieldCount);

        // Set field types and metadata based on PostgreSQL column types
        for (uint32 i = 0; i < m_fieldCount; ++i)
        {
            Oid fieldType = PQftype(m_result, i);
            m_fieldOids[i] = fieldType;

            // Populate field metadata
            m_fieldMetadata[i].TableName = "";  // PostgreSQL doesn't provide table name in results
            m_fieldMetadata[i].TableAlias = "";
            m_fieldMetadata[i].Name = PQfname(m_result, i);
            m_fieldMetadata[i].Alias = PQfname(m_result, i);
            m_fieldMetadata[i].TypeName = "";
            m_fieldMetadata[i].Index = i;
            m_fieldMetadata[i].Type = ConvertPostgreSQLType(fieldType);

            // PostgreSQL always returns text format, so use string converters
            m_fieldMetadata[i].Converter = PostgreSQLStringConverters[AsUnderlyingType(m_fieldMetadata[i].Type)].get();

            // Set metadata for the field
            m_fields[i].SetMetadata(&m_fieldMetadata[i]);
        }

        // Pre-fetch the first row to match MySQL behavior
        // The common usage pattern is: do { Fetch(); } while (NextRow());
        // which expects the first row to be available before the first NextRow() call
        if (m_rowCount > 0)
            _NextRow();
    }
}

PreparedResultSet::~PreparedResultSet()
{
    CleanUp();
}

bool PreparedResultSet::NextRow()
{
    return _NextRow();
}

bool PreparedResultSet::_NextRow()
{
    if (!m_result)
        return false;

    if (++m_currentRowIndex >= static_cast<int>(m_rowCount))
        return false;

    // Update field values for current row
    for (uint32 i = 0; i < m_fieldCount; ++i)
    {
        if (PQgetisnull(m_result, m_currentRowIndex, i))
        {
            m_fields[i].SetValue(nullptr, 0);
        }
        else
        {
            char* value = PQgetvalue(m_result, m_currentRowIndex, i);
            int length = PQgetlength(m_result, m_currentRowIndex, i);

            // Decode bytea columns from hex format to raw binary
            if (m_fieldOids[i] == BYTEAOID && length > 0)
            {
                DecodeByteaHex(value, length, m_byteaBuffers[i]);
                m_fields[i].SetValue(reinterpret_cast<char const*>(m_byteaBuffers[i].data()),
                                     static_cast<uint32>(m_byteaBuffers[i].size()));
            }
            else
            {
                m_fields[i].SetValue(value, length);
            }
        }
    }

    return true;
}

Field const& PreparedResultSet::operator[](std::size_t index) const
{
    ASSERT(index < m_fieldCount);
    return m_fields[index];
}

QueryResultFieldMetadata const& PreparedResultSet::GetFieldMetadata(std::size_t index) const
{
    ASSERT(index < m_fieldCount);
    return m_fieldMetadata[index];
}

void PreparedResultSet::CleanUp()
{
    if (m_result)
    {
        PQclear(m_result);
        m_result = nullptr;
    }
    m_currentRowData = nullptr;
}