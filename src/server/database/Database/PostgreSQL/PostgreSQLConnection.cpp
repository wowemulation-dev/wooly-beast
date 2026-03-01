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

#include "PostgreSQLConnection.h"
#include "Common.h"
#include "IoContext.h"
#include "Log.h"
#include "PostgreSQLPreparedStatement.h"
#include "PostgreSQLResultSet.h"
#include "PreparedStatement.h"
#include "QueryResult.h"
#include "StringConvert.h"
#include "Timer.h"
#include "Transaction.h"
#include "Util.h"
#include <sstream>
#include <thread>

PostgreSQLConnectionInfo::PostgreSQLConnectionInfo(std::string const& infoString)
{
    std::vector<std::string_view> tokens = Trinity::Tokenize(infoString, ';', true);

    if (tokens.size() != 5 && tokens.size() != 6)
        return;

    host.assign(tokens[0]);
    port_or_socket.assign(tokens[1]);
    user.assign(tokens[2]);
    password.assign(tokens[3]);
    database.assign(tokens[4]);

    if (tokens.size() == 6)
        ssl.assign(tokens[5]);
}

struct PostgreSQLConnection::WorkerThread
{
    std::thread ThreadHandle;
    boost::asio::executor_work_guard<Trinity::Asio::IoContext::Executor> WorkGuard;
};

PostgreSQLConnection::PostgreSQLConnection(PostgreSQLConnectionInfo& connInfo, ConnectionFlags connectionFlags) :
m_reconnecting(false),
m_prepareError(false),
m_conn(nullptr),
m_connectionInfo(connInfo),
m_connectionFlags(connectionFlags)
{
}

PostgreSQLConnection::~PostgreSQLConnection()
{
    Close();
}

void PostgreSQLConnection::Close()
{
    if (m_workerThread)
    {
        m_workerThread->WorkGuard.reset();
        m_workerThread->ThreadHandle.join();
        m_workerThread.reset();
    }

    m_stmts.clear();

    if (m_conn)
    {
        PQfinish(m_conn);
        m_conn = nullptr;
    }
}

uint32 PostgreSQLConnection::Open()
{
    std::stringstream connStr;
    connStr << "host=" << m_connectionInfo.host
            << " port=" << m_connectionInfo.port_or_socket
            << " dbname=" << m_connectionInfo.database
            << " user=" << m_connectionInfo.user
            << " password=" << m_connectionInfo.password
            << " connect_timeout=10"
            << " client_encoding=UTF8";

    if (!m_connectionInfo.ssl.empty() && m_connectionInfo.ssl == "ssl")
        connStr << " sslmode=require";

    m_conn = PQconnectdb(connStr.str().c_str());

    if (PQstatus(m_conn) != CONNECTION_OK)
    {
        std::string error_msg = PQerrorMessage(m_conn);
        TC_LOG_ERROR("sql.sql", "Could not connect to PostgreSQL database at {}:{} - {}",
            m_connectionInfo.host, m_connectionInfo.port_or_socket, error_msg);

        if (error_msg.find("database") != std::string::npos &&
            error_msg.find("does not exist") != std::string::npos)
        {
            PQfinish(m_conn);
            m_conn = nullptr;
            return 1049; // ER_BAD_DB_ERROR equivalent
        }

        PQfinish(m_conn);
        m_conn = nullptr;
        return 1;
    }

    PQsetClientEncoding(m_conn, "UTF8");

    if (!m_reconnecting)
    {
        TC_LOG_INFO("sql.sql", "PostgreSQL client library: {}", PQlibVersion());
        TC_LOG_INFO("sql.sql", "PostgreSQL server ver: {}", PQserverVersion(m_conn));
    }

    TC_LOG_INFO("sql.sql", "Connected to PostgreSQL database at {}", m_connectionInfo.host);

    return 0;
}

bool PostgreSQLConnection::PrepareStatements()
{
    DoPrepareStatements();
    return !m_prepareError;
}

bool PostgreSQLConnection::Execute(char const* sql)
{
    if (!m_conn)
        return false;

    uint32 _s = getMSTime();

    PGresult* result = PQexec(m_conn, sql);
    if (!result)
        return false;

    ExecStatusType status = PQresultStatus(result);
    bool success = (status == PGRES_COMMAND_OK || status == PGRES_TUPLES_OK);

    if (!success)
    {
        TC_LOG_INFO("sql.sql", "SQL: {}", sql);
        TC_LOG_ERROR("sql.sql", "PostgreSQL error: {}", PQresultErrorMessage(result));

        if (_HandlePostgreSQLError())
        {
            PQclear(result);
            return Execute(sql);
        }

        PQclear(result);
        return false;
    }

    TC_LOG_DEBUG("sql.sql", "[{} ms] SQL: {}", getMSTimeDiff(_s, getMSTime()), sql);

    PQclear(result);
    return true;
}

bool PostgreSQLConnection::Execute(PreparedStatementBase* stmt)
{
    if (!m_conn || !stmt)
        return false;

    uint32 index = stmt->GetIndex();

    PostgreSQLPreparedStatement* pgStmt = GetPreparedStatement(index);
    ASSERT(pgStmt);

    pgStmt->BindParameters(stmt);

    uint32 _s = getMSTime();

    PGresult* result = PQexecPrepared(m_conn,
                                      pgStmt->GetStmtName().c_str(),
                                      pgStmt->GetParameterCount(),
                                      pgStmt->GetParamValues().data(),
                                      pgStmt->GetParamLengths().data(),
                                      pgStmt->GetParamFormats().data(),
                                      0);

    if (!result)
    {
        pgStmt->ClearParameters();
        return false;
    }

    ExecStatusType status = PQresultStatus(result);
    bool success = (status == PGRES_COMMAND_OK || status == PGRES_TUPLES_OK);

    if (!success)
    {
        TC_LOG_ERROR("sql.sql", "SQL(p): {}\n [ERROR]: {}", pgStmt->getQueryString(), PQresultErrorMessage(result));

        if (_HandlePostgreSQLError())
        {
            PQclear(result);
            pgStmt->ClearParameters();
            return Execute(stmt);
        }

        PQclear(result);
        pgStmt->ClearParameters();
        return false;
    }

    TC_LOG_DEBUG("sql.sql", "[{} ms] SQL(p): {}", getMSTimeDiff(_s, getMSTime()), pgStmt->getQueryString());

    PQclear(result);
    pgStmt->ClearParameters();
    return true;
}

ResultSet* PostgreSQLConnection::Query(char const* sql)
{
    if (!sql)
        return nullptr;

    PGresult* result = nullptr;
    uint64 rowCount = 0;
    uint32 fieldCount = 0;

    if (!_Query(sql, &result, &rowCount, &fieldCount))
        return nullptr;

    if (!rowCount)
    {
        PQclear(result);
        return nullptr;
    }

    return new ResultSet(result, rowCount, fieldCount);
}

PreparedResultSet* PostgreSQLConnection::Query(PreparedStatementBase* stmt)
{
    if (!m_conn || !stmt)
        return nullptr;

    PostgreSQLPreparedStatement* pgStmt = nullptr;
    PGresult* result = nullptr;
    uint64 rowCount = 0;
    uint32 fieldCount = 0;

    if (!_Query(stmt, &pgStmt, &result, &rowCount, &fieldCount))
        return nullptr;

    if (!rowCount)
    {
        PQclear(result);
        return nullptr;
    }

    return new PreparedResultSet(result, rowCount, fieldCount);
}

bool PostgreSQLConnection::_Query(char const* sql, PGresult** pResult, uint64* pRowCount, uint32* pFieldCount)
{
    if (!m_conn)
        return false;

    uint32 _s = getMSTime();

    PGresult* result = PQexec(m_conn, sql);
    if (!result)
        return false;

    ExecStatusType status = PQresultStatus(result);
    if (status != PGRES_TUPLES_OK)
    {
        TC_LOG_INFO("sql.sql", "SQL: {}", sql);
        TC_LOG_ERROR("sql.sql", "PostgreSQL error: {}", PQresultErrorMessage(result));

        if (_HandlePostgreSQLError())
        {
            PQclear(result);
            return _Query(sql, pResult, pRowCount, pFieldCount);
        }

        PQclear(result);
        return false;
    }

    TC_LOG_DEBUG("sql.sql", "[{} ms] SQL: {}", getMSTimeDiff(_s, getMSTime()), sql);

    uint64 rowCount = PQntuples(result);
    uint32 fieldCount = PQnfields(result);

    if (!rowCount)
    {
        PQclear(result);
        return false;
    }

    if (pResult)
        *pResult = result;
    else
        PQclear(result);

    if (pRowCount)
        *pRowCount = rowCount;

    if (pFieldCount)
        *pFieldCount = fieldCount;

    return true;
}

bool PostgreSQLConnection::_Query(PreparedStatementBase* stmt, PostgreSQLPreparedStatement** pgStmt, PGresult** pResult, uint64* pRowCount, uint32* pFieldCount)
{
    if (!m_conn || !stmt)
        return false;

    uint32 index = stmt->GetIndex();

    PostgreSQLPreparedStatement* pStmt = GetPreparedStatement(index);
    ASSERT(pStmt);

    pStmt->BindParameters(stmt);
    *pgStmt = pStmt;

    uint32 _s = getMSTime();

    PGresult* result = PQexecPrepared(m_conn,
                                      pStmt->GetStmtName().c_str(),
                                      pStmt->GetParameterCount(),
                                      pStmt->GetParamValues().data(),
                                      pStmt->GetParamLengths().data(),
                                      pStmt->GetParamFormats().data(),
                                      0);

    if (!result)
    {
        pStmt->ClearParameters();
        return false;
    }

    ExecStatusType status = PQresultStatus(result);
    if (status != PGRES_TUPLES_OK)
    {
        TC_LOG_ERROR("sql.sql", "SQL(p): {}\n [ERROR]: {}", pStmt->getQueryString(), PQresultErrorMessage(result));

        if (_HandlePostgreSQLError())
        {
            PQclear(result);
            pStmt->ClearParameters();
            return _Query(stmt, pgStmt, pResult, pRowCount, pFieldCount);
        }

        PQclear(result);
        pStmt->ClearParameters();
        return false;
    }

    TC_LOG_DEBUG("sql.sql", "[{} ms] SQL(p): {}", getMSTimeDiff(_s, getMSTime()), pStmt->getQueryString());

    pStmt->ClearParameters();

    uint64 rowCount = PQntuples(result);
    uint32 fieldCount = PQnfields(result);

    if (pResult)
        *pResult = result;
    else
        PQclear(result);

    if (pRowCount)
        *pRowCount = rowCount;

    if (pFieldCount)
        *pFieldCount = fieldCount;

    return true;
}

void PostgreSQLConnection::BeginTransaction()
{
    Execute("BEGIN");
}

void PostgreSQLConnection::RollbackTransaction()
{
    Execute("ROLLBACK");
}

void PostgreSQLConnection::CommitTransaction()
{
    Execute("COMMIT");
}

int PostgreSQLConnection::ExecuteTransaction(std::shared_ptr<TransactionBase> transaction)
{
    std::vector<TransactionData> const& queries = transaction->m_queries;
    if (queries.empty())
        return -1;

    BeginTransaction();

    for (auto itr = queries.begin(); itr != queries.end(); ++itr)
    {
        if (!std::visit([this](auto&& data) { return this->Execute(TransactionData::ToExecutable(data)); }, itr->query))
        {
            TC_LOG_WARN("sql.sql", "Transaction aborted. {} queries not executed.", queries.size());
            int errorCode = GetLastError();
            RollbackTransaction();
            return errorCode;
        }
    }

    CommitTransaction();
    return 0;
}

size_t PostgreSQLConnection::EscapeString(char* to, const char* from, size_t length)
{
    if (!m_conn)
        return 0;

    int error = 0;
    size_t result = PQescapeStringConn(m_conn, to, from, length, &error);

    if (error)
    {
        TC_LOG_ERROR("sql.sql", "PostgreSQL escape string error");
        return 0;
    }

    return result;
}

void PostgreSQLConnection::Ping()
{
    if (!m_conn)
        return;

    PGresult* result = PQexec(m_conn, "SELECT 1");
    if (result)
        PQclear(result);
}

uint32 PostgreSQLConnection::GetLastError()
{
    // PostgreSQL uses SQLSTATE codes, not numeric error codes like MySQL.
    // Return 0 as a default; callers that need specific error handling
    // should check connection status directly.
    return 0;
}

void PostgreSQLConnection::StartWorkerThread(Trinity::Asio::IoContext* context)
{
    boost::asio::executor_work_guard executorWorkGuard = boost::asio::make_work_guard(context->get_executor());

    m_workerThread = std::make_unique<WorkerThread>(WorkerThread{
        .ThreadHandle = std::thread([context] { context->run(); }),
        .WorkGuard = std::move(executorWorkGuard)
    });
}

std::thread::id PostgreSQLConnection::GetWorkerThreadId() const
{
    if (m_workerThread)
        return m_workerThread->ThreadHandle.get_id();

    return {};
}

bool PostgreSQLConnection::LockIfReady()
{
    return m_Mutex.try_lock();
}

void PostgreSQLConnection::Unlock()
{
    m_Mutex.unlock();
}

uint32 PostgreSQLConnection::GetServerVersion() const
{
    if (!m_conn)
        return 0;

    return PQserverVersion(m_conn);
}

PostgreSQLPreparedStatement* PostgreSQLConnection::GetPreparedStatement(uint32 index)
{
    ASSERT(index < m_stmts.size(), "Tried to access invalid prepared statement index %u (max index " SZFMTD ") on database `%s`, connection type: %s",
        index, m_stmts.size(), m_connectionInfo.database.c_str(), (m_connectionFlags & CONNECTION_ASYNC) ? "asynchronous" : "synchronous");
    PostgreSQLPreparedStatement* ret = m_stmts[index].get();
    if (!ret)
        TC_LOG_ERROR("sql.sql", "Could not fetch prepared statement {} on database `{}`, connection type: {}.",
            index, m_connectionInfo.database, (m_connectionFlags & CONNECTION_ASYNC) ? "asynchronous" : "synchronous");

    return ret;
}

void PostgreSQLConnection::PrepareStatement(uint32 index, std::string_view sql, ConnectionFlags flags)
{
    if (!(m_connectionFlags & flags))
    {
        m_stmts[index].reset();
        return;
    }

    auto pgStmt = std::make_unique<PostgreSQLPreparedStatement>(sql, m_conn);

    // Check if preparation succeeded by verifying the statement name was set
    if (pgStmt->GetStmtName().empty())
    {
        TC_LOG_ERROR("sql.sql", "In PostgreSQLConnection::PrepareStatement() id: {}, sql: \"{}\"", index, sql);
        m_prepareError = true;
    }
    else
        m_stmts[index] = std::move(pgStmt);
}

bool PostgreSQLConnection::_HandlePostgreSQLError(uint8 attempts)
{
    if (!m_conn)
        return false;

    ConnStatusType status = PQstatus(m_conn);
    if (status != CONNECTION_OK)
    {
        TC_LOG_ERROR("sql.sql", "Lost the connection to the PostgreSQL server!");

        PQfinish(m_conn);
        m_conn = nullptr;

        if (m_reconnecting)
            return false;

        TC_LOG_INFO("sql.sql", "Attempting to reconnect to the PostgreSQL server...");

        m_reconnecting = true;

        uint32 const lErrno = Open();
        if (!lErrno)
        {
            if (!this->PrepareStatements())
            {
                TC_LOG_FATAL("sql.sql", "Could not re-prepare statements!");
                std::this_thread::sleep_for(std::chrono::seconds(10));
                ABORT();
            }

            TC_LOG_INFO("sql.sql", "Successfully reconnected to {} @{}:{} ({}).",
                m_connectionInfo.database, m_connectionInfo.host, m_connectionInfo.port_or_socket,
                    (m_connectionFlags & CONNECTION_ASYNC) ? "asynchronous" : "synchronous");

            m_reconnecting = false;
            return true;
        }

        if ((--attempts) == 0)
        {
            TC_LOG_FATAL("sql.sql", "Failed to reconnect to the PostgreSQL server, "
                         "terminating the server to prevent data corruption!");

            std::this_thread::sleep_for(std::chrono::seconds(10));
            ABORT();
        }
        else
        {
            std::this_thread::sleep_for(std::chrono::seconds(3));
            return _HandlePostgreSQLError(attempts);
        }
    }

    return false;
}
