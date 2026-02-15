/**
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors
 */

#ifndef DATABASEENV_H
#define DATABASEENV_H

#include "Define.h"
#include "DatabaseWorkerPool.h"

// Macro for quoting SQL identifiers (reserved words like "rank")
// MySQL uses backticks, PostgreSQL uses double quotes
#ifdef WITH_POSTGRESQL
#define DB_QUOTE_IDENT(x) "\"" x "\""
#else
#define DB_QUOTE_IDENT(x) "`" x "`"
#endif

#ifdef WITH_POSTGRESQL
#include "Implementation/PostgreSQL/LoginDatabase.h"
#include "Implementation/PostgreSQL/CharacterDatabase.h"
#include "Implementation/PostgreSQL/WorldDatabase.h"
#else
#include "Implementation/LoginDatabase.h"
#include "Implementation/CharacterDatabase.h"
#include "Implementation/WorldDatabase.h"
#endif

#include "Field.h"
#include "PreparedStatement.h"
#include "QueryCallback.h"
#include "QueryResult.h"
#include "Transaction.h"

/// Accessor to the world database
TC_DATABASE_API extern DatabaseWorkerPool<WorldDatabaseConnection> WorldDatabase;
/// Accessor to the character database
TC_DATABASE_API extern DatabaseWorkerPool<CharacterDatabaseConnection> CharacterDatabase;
/// Accessor to the realm/login database
TC_DATABASE_API extern DatabaseWorkerPool<LoginDatabaseConnection> LoginDatabase;

#endif
