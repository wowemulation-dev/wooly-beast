/**
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors
 */

#ifndef _POSTGRESQLCONNECTION_H
#define _POSTGRESQLCONNECTION_H

#include "Define.h"
#include "DatabaseEnvFwd.h"
#include <libpq-fe.h>

#ifndef WITH_POSTGRESQL
#error "This file should only be included when WITH_POSTGRESQL is defined"
#endif

// Define connection flags if not already defined
#ifndef CONNECTION_FLAGS_DEFINED
#define CONNECTION_FLAGS_DEFINED
enum ConnectionFlags
{
    CONNECTION_ASYNC = 0x01,
    CONNECTION_SYNCH = 0x02,
    CONNECTION_BOTH = CONNECTION_ASYNC | CONNECTION_SYNCH
};
#endif
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

template <typename T>
class ProducerConsumerQueue;

class DatabaseWorker;
class PostgreSQLPreparedStatement;
class SQLOperation;

// ConnectionFlags enum is defined in MySQLConnection.h

struct TC_DATABASE_API PostgreSQLConnectionInfo
{
    explicit PostgreSQLConnectionInfo(std::string const& infoString);

    std::string user;
    std::string password;
    std::string database;
    std::string host;
    std::string port;
    std::string port_or_socket;  // Alias for port for compatibility
    std::string schema;
    std::string ssl;  // SSL mode for compatibility
};

class TC_DATABASE_API PostgreSQLConnection
{
    template <class T> friend class DatabaseWorkerPool;
    friend class PingOperation;

    public:
        PostgreSQLConnection(PostgreSQLConnectionInfo& connInfo);                               //! Constructor for synchronous connections.
        PostgreSQLConnection(ProducerConsumerQueue<SQLOperation*>* queue, PostgreSQLConnectionInfo& connInfo);  //! Constructor for asynchronous connections.
        virtual ~PostgreSQLConnection();

        virtual uint32 Open();
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

    protected:
        /// Tries to acquire lock. If lock is acquired by another thread
        /// the calling parent will just try another connection
        bool LockIfReady();

        /// Called by parent databasepool. Will let other threads access this connection
        void Unlock();

        uint32 GetServerVersion() const;
        PostgreSQLPreparedStatement* GetPreparedStatement(uint32 index);
        void PrepareStatement(uint32 index, std::string const& sql, ConnectionFlags flags);

        virtual void DoPrepareStatements() = 0;

        typedef std::vector<std::unique_ptr<PostgreSQLPreparedStatement>> PreparedStatementContainer;

        PreparedStatementContainer           m_stmts;         //! PreparedStatements storage
        bool                                 m_reconnecting;  //! Are we reconnecting?
        bool                                 m_prepareError;  //! Was there any error while preparing statements?

    private:
        bool _HandlePostgreSQLError(const char* operation, uint8 attempts = 5);

        ProducerConsumerQueue<SQLOperation*>* m_queue;      //! Queue shared with other asynchronous connections.
        std::unique_ptr<DatabaseWorker> m_worker;           //! Core worker task.
        PGconn*               m_conn;                       //! PostgreSQL Handle.
        PostgreSQLConnectionInfo& m_connectionInfo;         //! Connection info (used for logging)
        ConnectionFlags       m_connectionFlags;            //! Connection flags (for preparing relevant statements)
        std::mutex            m_Mutex;

        PostgreSQLConnection(PostgreSQLConnection const& right) = delete;
        PostgreSQLConnection& operator=(PostgreSQLConnection const& right) = delete;
};

#endif