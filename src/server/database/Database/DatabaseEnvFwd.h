/**
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors
 */

#ifndef DatabaseEnvFwd_h__
#define DatabaseEnvFwd_h__

#include "AsyncCallbackProcessorFwd.h"
#include <future>
#include <memory>

struct QueryResultFieldMetadata;
class Field;

class ResultSet;
using QueryResult = std::shared_ptr<ResultSet>;
using QueryResultFuture = std::future<QueryResult>;
using QueryResultPromise = std::promise<QueryResult>;

#ifdef WITH_POSTGRESQL
class PostgreSQLCharacterDatabaseConnection;
class PostgreSQLLoginDatabaseConnection;
class PostgreSQLWorldDatabaseConnection;
typedef PostgreSQLCharacterDatabaseConnection CharacterDatabaseConnection;
typedef PostgreSQLLoginDatabaseConnection LoginDatabaseConnection;
typedef PostgreSQLWorldDatabaseConnection WorldDatabaseConnection;
#else
class CharacterDatabaseConnection;
class LoginDatabaseConnection;
class WorldDatabaseConnection;
#endif

class PreparedStatementBase;

template<typename T>
class PreparedStatement;

using CharacterDatabasePreparedStatement = PreparedStatement<CharacterDatabaseConnection>;
using LoginDatabasePreparedStatement = PreparedStatement<LoginDatabaseConnection>;
using WorldDatabasePreparedStatement = PreparedStatement<WorldDatabaseConnection>;

class PreparedResultSet;
using PreparedQueryResult = std::shared_ptr<PreparedResultSet>;
using PreparedQueryResultFuture = std::future<PreparedQueryResult>;
using PreparedQueryResultPromise = std::promise<PreparedQueryResult>;

class QueryCallback;
bool InvokeAsyncCallbackIfReady(QueryCallback& callback);

using QueryCallbackProcessor = AsyncCallbackProcessor<QueryCallback>;

class TransactionBase;

using TransactionFuture = std::future<bool>;
using TransactionPromise = std::promise<bool>;

template<typename T>
class Transaction;

class TransactionCallback;
bool InvokeAsyncCallbackIfReady(TransactionCallback& callback);

template<typename T>
using SQLTransaction = std::shared_ptr<Transaction<T>>;

using CharacterDatabaseTransaction = SQLTransaction<CharacterDatabaseConnection>;
using LoginDatabaseTransaction = SQLTransaction<LoginDatabaseConnection>;
using WorldDatabaseTransaction = SQLTransaction<WorldDatabaseConnection>;

class SQLQueryHolderBase;
using QueryResultHolderFuture = std::future<void>;
using QueryResultHolderPromise = std::promise<void>;

template<typename T>
class SQLQueryHolder;

using CharacterDatabaseQueryHolder = SQLQueryHolder<CharacterDatabaseConnection>;
using LoginDatabaseQueryHolder = SQLQueryHolder<LoginDatabaseConnection>;
using WorldDatabaseQueryHolder = SQLQueryHolder<WorldDatabaseConnection>;

class SQLQueryHolderCallback;
bool InvokeAsyncCallbackIfReady(SQLQueryHolderCallback& callback);

// mysql
struct MySQLHandle;
struct MySQLResult;
struct MySQLField;
struct MySQLBind;
struct MySQLStmt;

#endif // DatabaseEnvFwd_h__
