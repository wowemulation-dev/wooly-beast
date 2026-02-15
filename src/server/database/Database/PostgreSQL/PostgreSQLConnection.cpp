/**
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors
 */

#include "PostgreSQLConnection.h"
#include "PostgreSQLPreparedStatement.h"
#include "PostgreSQLResultSet.h"
#include "PostgreSQLField.h"
#include "Log.h"
#include "Common.h"
#include "PreparedStatement.h"
#include "Transaction.h"
#include "QueryHolder.h"
#include "DatabaseWorker.h"
#include "Timer.h"
#include "Util.h"
#include <sstream>
#include <regex>
#include <thread>

PostgreSQLConnectionInfo::PostgreSQLConnectionInfo(std::string const& infoString)
{
    // Parse connection string format: "host;port;user;password;database[;ssl]"
    // This matches the MySQL format for consistency
    std::vector<std::string_view> tokens = Trinity::Tokenize(infoString, ';', true);

    if (tokens.size() != 5 && tokens.size() != 6)
    {
        TC_LOG_ERROR("sql.driver", "Invalid PostgreSQL connection string format. Expected: host;port;user;password;database[;ssl]");
        return;
    }

    host.assign(tokens[0]);
    port.assign(tokens[1]);
    port_or_socket.assign(tokens[1]);  // Set alias for compatibility
    user.assign(tokens[2]);
    password.assign(tokens[3]);
    database.assign(tokens[4]);

    if (tokens.size() == 6)
        ssl.assign(tokens[5]);

    // Default schema
    schema = "public";
}

PostgreSQLConnection::PostgreSQLConnection(PostgreSQLConnectionInfo& connInfo)
    : m_reconnecting(false)
    , m_prepareError(false)
    , m_queue(nullptr)
    , m_conn(nullptr)
    , m_connectionInfo(connInfo)
    , m_connectionFlags(CONNECTION_SYNCH)
{
}

PostgreSQLConnection::PostgreSQLConnection(ProducerConsumerQueue<SQLOperation*>* queue, PostgreSQLConnectionInfo& connInfo)
    : m_reconnecting(false)
    , m_prepareError(false)
    , m_queue(queue)
    , m_conn(nullptr)
    , m_connectionInfo(connInfo)
    , m_connectionFlags(CONNECTION_ASYNC)
{
    m_worker = std::make_unique<DatabaseWorker>(m_queue, this);
}

PostgreSQLConnection::~PostgreSQLConnection()
{
    Close();
}

uint32 PostgreSQLConnection::Open()
{
    // Build PostgreSQL connection string
    std::stringstream connStr;
    connStr << "host=" << m_connectionInfo.host
            << " port=" << m_connectionInfo.port
            << " dbname=" << m_connectionInfo.database
            << " user=" << m_connectionInfo.user
            << " password=" << m_connectionInfo.password
            << " connect_timeout=10"
            << " client_encoding=UTF8";
    
    m_conn = PQconnectdb(connStr.str().c_str());
    
    if (PQstatus(m_conn) != CONNECTION_OK)
    {
        std::string error_msg = PQerrorMessage(m_conn);
        TC_LOG_ERROR("sql.driver", "Could not connect to PostgreSQL database at {}:{} - {}",
            m_connectionInfo.host.c_str(), m_connectionInfo.port.c_str(), error_msg);

        // Check if the error is because the database doesn't exist
        // PostgreSQL returns: FATAL:  database "xxx" does not exist
        if (error_msg.find("database") != std::string::npos &&
            error_msg.find("does not exist") != std::string::npos)
        {
            PQfinish(m_conn);
            m_conn = nullptr;
            return 1049;  // Return MySQL's ER_BAD_DB_ERROR for compatibility
        }

        PQfinish(m_conn);
        m_conn = nullptr;
        return 1;
    }
    
    // Set schema if not default
    if (m_connectionInfo.schema != "public")
    {
        std::string setSchema = "SET search_path TO " + m_connectionInfo.schema;
        if (!Execute(setSchema.c_str()))
        {
            TC_LOG_ERROR("sql.driver", "Failed to set schema to {}", m_connectionInfo.schema.c_str());
            Close();
            return 1;
        }
    }
    
    // Set client encoding
    PQsetClientEncoding(m_conn, "UTF8");
    
    TC_LOG_INFO("sql.driver", "PostgreSQL client version: {}", PQlibVersion());
    TC_LOG_INFO("sql.driver", "PostgreSQL server version: {}", PQserverVersion(m_conn));
    TC_LOG_INFO("sql.driver", "Connected to PostgreSQL database at {}:{}",
        m_connectionInfo.host.c_str(), m_connectionInfo.port.c_str());
    
    return 0;
}

void PostgreSQLConnection::Close()
{
    if (m_conn)
    {
        PQfinish(m_conn);
        m_conn = nullptr;
    }
}

bool PostgreSQLConnection::PrepareStatements()
{
    DoPrepareStatements();
    return !m_prepareError;
}

void PostgreSQLConnection::Ping()
{
    if (!m_conn)
        return;
        
    PGresult* result = PQexec(m_conn, "SELECT 1");
    if (!result)
        return;
        
    PQclear(result);
}

uint32 PostgreSQLConnection::GetLastError()
{
    if (!m_conn)
        return 0;
        
    // PostgreSQL doesn't have numeric error codes like MySQL
    // We could map SQLSTATE codes if needed
    return 0;
}

bool PostgreSQLConnection::Execute(char const* sql)
{
    if (!m_conn)
        return false;

    PGresult* result = PQexec(m_conn, sql);
    if (!result)
        return false;

    ExecStatusType status = PQresultStatus(result);
    bool success = (status == PGRES_COMMAND_OK || status == PGRES_TUPLES_OK);

    if (!success)
    {
        // Get detailed error information
        char const* errorMessage = PQresultErrorMessage(result);
        if (!errorMessage || !*errorMessage)
            errorMessage = PQerrorMessage(m_conn);

        // Get SQLSTATE error code
        char const* sqlState = PQresultErrorField(result, PG_DIAG_SQLSTATE);

        TC_LOG_ERROR("sql.driver", "PostgreSQL execute error: {} (SQLSTATE: {})",
                     errorMessage, sqlState ? sqlState : "unknown");

        // Only log first 500 characters of SQL to avoid massive log spam with large SQL files
        size_t sqlLen = strlen(sql);
        if (sqlLen <= 500)
        {
            TC_LOG_ERROR("sql.sql", "SQL: {}", sql);
        }
        else
        {
            std::string truncated(sql, 500);
            TC_LOG_ERROR("sql.sql", "SQL (truncated, {} total chars): {}...", sqlLen, truncated);
        }

        // Log additional diagnostic information if available
        char const* detail = PQresultErrorField(result, PG_DIAG_MESSAGE_DETAIL);
        if (detail)
            TC_LOG_ERROR("sql.driver", "Detail: {}", detail);

        char const* hint = PQresultErrorField(result, PG_DIAG_MESSAGE_HINT);
        if (hint)
            TC_LOG_ERROR("sql.driver", "Hint: {}", hint);
    }

    PQclear(result);
    return success;
}

bool PostgreSQLConnection::Execute(PreparedStatementBase* stmt)
{
    if (!m_conn || !stmt)
        return false;

    PostgreSQLPreparedStatement* pgStmt = nullptr;
    if (!_Query(stmt, &pgStmt, nullptr, nullptr, nullptr))
        return false;

    return true;
}

ResultSet* PostgreSQLConnection::Query(char const* sql)
{
    if (!m_conn)
        return nullptr;

    PGresult* result = nullptr;
    uint64 rowCount = 0;
    uint32 fieldCount = 0;

    if (!_Query(sql, &result, &rowCount, &fieldCount))
        return nullptr;

    // Return nullptr for empty result sets to match MySQL behavior
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

    PGresult* result = PQexec(m_conn, sql);
    if (!result)
        return false;

    ExecStatusType status = PQresultStatus(result);
    if (status != PGRES_COMMAND_OK && status != PGRES_TUPLES_OK)
    {
        TC_LOG_ERROR("sql.driver", "PostgreSQL query error: {}", PQresultErrorMessage(result));
        TC_LOG_ERROR("sql.sql", "SQL: {}", sql);
        PQclear(result);
        return false;
    }

    if (pResult)
        *pResult = result;
    else
        PQclear(result);

    if (pRowCount)
        *pRowCount = PQntuples(result);

    if (pFieldCount)
        *pFieldCount = PQnfields(result);

    return true;
}

bool PostgreSQLConnection::_Query(PreparedStatementBase* stmt, PostgreSQLPreparedStatement** pgStmt, PGresult** pResult, uint64* pRowCount, uint32* pFieldCount)
{
    if (!m_conn || !stmt)
        return false;

    PostgreSQLPreparedStatement* pStmt = GetPreparedStatement(stmt->GetIndex());
    if (!pStmt)
    {
        TC_LOG_ERROR("sql.sql", "PostgreSQL prepared statement {} not found", stmt->GetIndex());
        return false;
    }

    pStmt->BindParameters(stmt);

    PGresult* result = PQexecPrepared(m_conn,
                                      pStmt->GetStmtName().c_str(),
                                      pStmt->GetParameterCount(),
                                      pStmt->GetParamValues().data(),
                                      pStmt->GetParamLengths().data(),
                                      pStmt->GetParamFormats().data(),
                                      0); // Result format (0 = text)

    if (!result)
        return false;

    ExecStatusType status = PQresultStatus(result);
    if (status != PGRES_COMMAND_OK && status != PGRES_TUPLES_OK)
    {
        TC_LOG_ERROR("sql.driver", "PostgreSQL prepared statement error: {}", PQresultErrorMessage(result));
        TC_LOG_ERROR("sql.sql", "SQL: {}", pStmt->getQueryString().c_str());
        PQclear(result);
        return false;
    }

    if (pgStmt)
        *pgStmt = pStmt;

    if (pResult)
        *pResult = result;
    else
        PQclear(result);

    if (pRowCount)
        *pRowCount = PQntuples(result);

    if (pFieldCount)
        *pFieldCount = PQnfields(result);

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
    if (!m_conn || !transaction)
        return -1;

    BeginTransaction();

    std::vector<SQLElementData> const& queries = transaction->m_queries;
    for (auto const& data : queries)
    {
        switch (data.type)
        {
            case SQL_ELEMENT_PREPARED:
            {
                PreparedStatementBase* stmt = data.element.stmt;
                if (!Execute(stmt))
                {
                    TC_LOG_ERROR("sql.sql", "Transaction aborted. {} queries not executed.", (uint32)queries.size());
                    RollbackTransaction();
                    return -1;
                }
            }
            break;
            case SQL_ELEMENT_RAW:
            {
                char const* sql = data.element.query;
                if (!Execute(sql))
                {
                    TC_LOG_ERROR("sql.sql", "Transaction aborted. {} queries not executed.", (uint32)queries.size());
                    RollbackTransaction();
                    return -1;
                }
            }
            break;
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
        TC_LOG_ERROR("sql.driver", "PostgreSQL escape string error");
        return 0;
    }

    return result;
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
    if (index >= m_stmts.size())
        return nullptr;
        
    return m_stmts[index].get();
}

void PostgreSQLConnection::PrepareStatement(uint32 index, std::string const& sql, ConnectionFlags flags)
{
    // Check if this statement should be prepared for this connection type
    if (!(m_connectionFlags & flags))
        return;

    if (index >= m_stmts.size())
        m_stmts.resize(index + 1);

    m_stmts[index] = std::make_unique<PostgreSQLPreparedStatement>(sql, m_conn);
}

bool PostgreSQLConnection::_HandlePostgreSQLError(const char* operation, uint8 attempts)
{
    if (!m_conn)
        return false;

    char const* error = PQerrorMessage(m_conn);
    if (!error || !*error)
        return true;

    ConnStatusType status = PQstatus(m_conn);
    if (status != CONNECTION_OK)
    {
        TC_LOG_ERROR("sql.driver", "Lost connection to PostgreSQL database. Operation: {}", operation);
        
        if (m_reconnecting)
            return false;

        if (attempts == 0)
            return false;

        // Try to reconnect
        m_reconnecting = true;
        uint32 reconnectAttempts = 0;
        
        while (reconnectAttempts < attempts)
        {
            TC_LOG_INFO("sql.driver", "Attempting to reconnect to PostgreSQL database (attempt {}/{})",
                reconnectAttempts + 1, attempts);
            
            Close();
            
            if (Open() == 0)
            {
                TC_LOG_INFO("sql.driver", "Successfully reconnected to PostgreSQL database");
                m_reconnecting = false;
                
                // Re-prepare statements after reconnection
                if (!PrepareStatements())
                {
                    TC_LOG_ERROR("sql.driver", "Failed to re-prepare statements after reconnection");
                    return false;
                }
                
                return true;
            }
            
            std::this_thread::sleep_for(std::chrono::seconds(3));
            ++reconnectAttempts;
        }
        
        m_reconnecting = false;
        return false;
    }

    return false;
}