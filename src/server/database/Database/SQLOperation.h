/**
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors
 */

#ifndef _SQLOPERATION_H
#define _SQLOPERATION_H

#include "Define.h"
#include "DatabaseEnvFwd.h"

//- Union that holds element data
union SQLElementUnion
{
    PreparedStatementBase* stmt;
    char const* query;
};

//- Type specifier of our element data
enum SQLElementDataType
{
    SQL_ELEMENT_RAW,
    SQL_ELEMENT_PREPARED
};

//- The element
struct SQLElementData
{
    SQLElementUnion element;
    SQLElementDataType type;
};

#ifdef WITH_POSTGRESQL
class PostgreSQLConnection;
typedef PostgreSQLConnection DatabaseConnection;
#else
class MySQLConnection;
typedef MySQLConnection DatabaseConnection;
#endif

class TC_DATABASE_API SQLOperation
{
    public:
        SQLOperation(): m_conn(nullptr) { }
        virtual ~SQLOperation() { }

        virtual int call()
        {
            Execute();
            return 0;
        }
        virtual bool Execute() = 0;
        virtual void SetConnection(DatabaseConnection* con) { m_conn = con; }

        DatabaseConnection* m_conn;

    private:
        SQLOperation(SQLOperation const& right) = delete;
        SQLOperation& operator=(SQLOperation const& right) = delete;
};

#endif
