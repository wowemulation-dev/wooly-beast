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

#ifndef _POSTGRESQLPREPAREDSTATEMENT_H
#define _POSTGRESQLPREPAREDSTATEMENT_H

#include "DatabaseEnvFwd.h"
#include "Define.h"
#include "Duration.h"
#include <libpq-fe.h>
#include <string>
#include <vector>

class PostgreSQLConnection;
class PreparedStatementBase;

class TC_DATABASE_API PostgreSQLPreparedStatement
{
    friend class PostgreSQLConnection;
    friend class PreparedStatementBase;

    public:
        PostgreSQLPreparedStatement(std::string_view queryString, PGconn* conn);
        ~PostgreSQLPreparedStatement();

        void BindParameters(PreparedStatementBase* stmt);
        void ClearParameters();

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
        std::vector<char const*> const& GetParamValues() const { return m_paramValues; }
        std::vector<int> const& GetParamLengths() const { return m_paramLengths; }
        std::vector<int> const& GetParamFormats() const { return m_paramFormats; }

        PreparedStatementBase* m_stmt;
        void AssertValidIndex(uint8 index);
        std::string getQueryString() const;

    private:
        PGconn* m_conn;
        std::string m_stmtName;
        uint32 m_paramCount;
        std::vector<bool> m_paramsSet;
        std::string m_queryString;

        std::vector<char const*> m_paramValues;
        std::vector<int> m_paramLengths;
        std::vector<int> m_paramFormats;
        std::vector<std::string> m_paramStringStorage;

        PostgreSQLPreparedStatement(PostgreSQLPreparedStatement const& right) = delete;
        PostgreSQLPreparedStatement& operator=(PostgreSQLPreparedStatement const& right) = delete;
};

#endif
