/**
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors
 */

#ifndef _POSTGRESQL_QUERYRESULT_H
#define _POSTGRESQL_QUERYRESULT_H

#include "DatabaseEnvFwd.h"
#include "Field.h"
#include <memory>
#include <vector>

// Forward declarations for PostgreSQL types
struct pg_result;
typedef struct pg_result PGresult;

// No need for PostgreSQLField forward declaration

class ResultSet
{
public:
    explicit ResultSet(PGresult* result, uint64 rowCount, uint32 fieldCount);
    ~ResultSet();

    bool NextRow();
    uint64 GetRowCount() const { return m_rowCount; }
    uint32 GetFieldCount() const { return m_fieldCount; }
    
    Field* Fetch() const { return m_currentRowData; }
    Field const& operator[](std::size_t index) const;
    
    QueryResultFieldMetadata const& GetFieldMetadata(std::size_t index) const;

protected:
    std::vector<QueryResultFieldMetadata> _fieldMetadata;
    uint64 m_rowCount;
    Field* m_currentRowData;
    uint32 m_fieldCount;
    
private:
    void CleanUp();

    PGresult* m_result;
    int m_currentRowIndex;
    std::unique_ptr<Field[]> m_fields;

    // Storage for decoded bytea values (PostgreSQL returns hex-encoded text)
    std::vector<std::vector<uint8>> m_byteaBuffers;
    // Column OIDs to detect bytea columns
    std::vector<unsigned int> m_fieldOids;

    ResultSet(ResultSet const& right) = delete;
    ResultSet& operator=(ResultSet const& right) = delete;
};

class PreparedResultSet
{
public:
    explicit PreparedResultSet(PGresult* result, uint64 rowCount, uint32 fieldCount);
    ~PreparedResultSet();

    bool NextRow();
    uint64 GetRowCount() const { return m_rowCount; }
    uint32 GetFieldCount() const { return m_fieldCount; }
    
    Field* Fetch() const { return m_currentRowData; }
    Field const& operator[](std::size_t index) const;
    
    QueryResultFieldMetadata const& GetFieldMetadata(std::size_t index) const;

protected:
    std::vector<QueryResultFieldMetadata> m_fieldMetadata;
    uint64 m_rowCount;
    Field* m_currentRowData;
    uint32 m_fieldCount;
    
private:
    void CleanUp();
    bool _NextRow();

    PGresult* m_result;
    int m_currentRowIndex;
    std::unique_ptr<Field[]> m_fields;

    // Storage for decoded bytea values (PostgreSQL returns hex-encoded text)
    std::vector<std::vector<uint8>> m_byteaBuffers;
    // Column OIDs to detect bytea columns
    std::vector<unsigned int> m_fieldOids;

    PreparedResultSet(PreparedResultSet const& right) = delete;
    PreparedResultSet& operator=(PreparedResultSet const& right) = delete;
};

#endif