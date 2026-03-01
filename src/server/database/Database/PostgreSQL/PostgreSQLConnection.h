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

#ifndef _POSTGRESQLCONNECTION_H
#define _POSTGRESQLCONNECTION_H

#include "AsioHacksFwd.h"
#include "DatabaseConnectionFlags.h"
#include "Define.h"
#include "DatabaseEnvFwd.h"
#include <libpq-fe.h>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

class PostgreSQLPreparedStatement;

struct TC_DATABASE_API PostgreSQLConnectionInfo
{
    explicit PostgreSQLConnectionInfo(std::string const& infoString);

    std::string user;
    std::string password;
    std::string database;
    std::string host;
    std::string port_or_socket;
    std::string ssl;
};

class TC_DATABASE_API PostgreSQLConnection
{
    template <class T> friend class DatabaseWorkerPool;
    friend class PingOperation;

    public:
        PostgreSQLConnection(PostgreSQLConnectionInfo& connInfo, ConnectionFlags connectionFlags);
        virtual ~PostgreSQLConnection();

        uint32 Open();
        void Close();

        bool PrepareStatements();

        bool Execute(char const* sql);
        bool Execute(PreparedStatementBase* stmt);
        ResultSet* Query(char const* sql);
        PreparedResultSet* Query(PreparedStatementBase* stmt);
        bool _Query(char const* sql, PGresult** pResult, uint64* pRowCount, uint32* pFieldCount);
        bool _Query(PreparedStatementBase* stmt, PostgreSQLPreparedStatement** pgStmt, PGresult** pResult, uint64* pRowCount, uint32* pFieldCount);

        void BeginTransaction();
        void RollbackTransaction();
        void CommitTransaction();
        int ExecuteTransaction(std::shared_ptr<TransactionBase> transaction);
        size_t EscapeString(char* to, const char* from, size_t length);
        void Ping();

        uint32 GetLastError();

        void StartWorkerThread(Trinity::Asio::IoContext* context);
        std::thread::id GetWorkerThreadId() const;

    protected:
        bool LockIfReady();
        void Unlock();

        uint32 GetServerVersion() const;
        PostgreSQLPreparedStatement* GetPreparedStatement(uint32 index);
        void PrepareStatement(uint32 index, std::string_view sql, ConnectionFlags flags);

        virtual void DoPrepareStatements() = 0;

        typedef std::vector<std::unique_ptr<PostgreSQLPreparedStatement>> PreparedStatementContainer;

        PreparedStatementContainer           m_stmts;
        bool                                 m_reconnecting;
        bool                                 m_prepareError;

    private:
        bool _HandlePostgreSQLError(uint8 attempts = 5);

        struct WorkerThread;
        std::unique_ptr<WorkerThread> m_workerThread;
        PGconn*                       m_conn;
        PostgreSQLConnectionInfo&     m_connectionInfo;
        ConnectionFlags               m_connectionFlags;
        std::mutex                    m_Mutex;

        PostgreSQLConnection(PostgreSQLConnection const& right) = delete;
        PostgreSQLConnection& operator=(PostgreSQLConnection const& right) = delete;
};

#endif
