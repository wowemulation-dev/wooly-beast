/**
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors
 */

#ifndef PostgreSQLPreparedStatement_h__
#define PostgreSQLPreparedStatement_h__

#include "DatabaseEnvFwd.h"
#include "Define.h"
#include "Duration.h"
#include <libpq-fe.h>
#include <string>
#include <vector>

class PostgreSQLConnection;
class PreparedStatementBase;

//- Class of which the instances are unique per PostgreSQLConnection
//- access to these class objects is only done when a prepared statement task
//- is executed.
class TC_DATABASE_API PostgreSQLPreparedStatement
{
    friend class PostgreSQLConnection;
    friend class PreparedStatementBase;

    public:
        PostgreSQLPreparedStatement(std::string queryString, PGconn* conn);
        ~PostgreSQLPreparedStatement();

        void BindParameters(PreparedStatementBase* stmt);

        uint32 GetParameterCount() const { return m_paramCount; }

    protected:
        void SetParameter(uint8 index, std::nullptr_t);
        void SetParameter(uint8 index, bool value);
        template<typename T>
        void SetParameter(uint8 index, T value);
        void SetParameter(uint8 index, SystemTimePoint value);
        void SetParameter(uint8 index, std::string const& value);
        void SetParameter(uint8 index, std::vector<uint8> const& value);

        std::string const& GetStmtName() const { return m_stmtName; }
        std::vector<char*> const& GetParamValues() const { return m_paramValues; }
        std::vector<int> const& GetParamLengths() const { return m_paramLengths; }
        std::vector<int> const& GetParamFormats() const { return m_paramFormats; }
        
        PreparedStatementBase* m_stmt;
        void ClearParameters();
        void AssertValidIndex(uint8 index);
        std::string getQueryString() const;

    private:
        PGconn* m_conn;
        std::string m_stmtName;
        uint32 m_paramCount;
        std::vector<bool> m_paramsSet;
        std::string m_queryString;
        
        // PostgreSQL specific parameter storage
        std::vector<char*> m_paramValues;
        std::vector<int> m_paramLengths;
        std::vector<int> m_paramFormats;
        std::vector<std::string> m_paramStringStorage;

        PostgreSQLPreparedStatement(PostgreSQLPreparedStatement const& right) = delete;
        PostgreSQLPreparedStatement& operator=(PostgreSQLPreparedStatement const& right) = delete;
};

#endif // PostgreSQLPreparedStatement_h__