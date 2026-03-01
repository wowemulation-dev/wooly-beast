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

#ifndef DATABASEENV_H
#define DATABASEENV_H

#include "Define.h"
#include "DatabaseWorkerPool.h"

#ifdef WITH_POSTGRESQL
#define DB_QUOTE_IDENT(x) "\"" x "\""
#else
#define DB_QUOTE_IDENT(x) "`" x "`"
#endif

#ifdef WITH_POSTGRESQL
#include "Implementation/PostgreSQL/LoginDatabase.h"
#include "Implementation/PostgreSQL/CharacterDatabase.h"
#include "Implementation/PostgreSQL/WorldDatabase.h"
#include "Implementation/PostgreSQL/HotfixDatabase.h"
#else
#include "Implementation/MySQL/LoginDatabase.h"
#include "Implementation/MySQL/CharacterDatabase.h"
#include "Implementation/MySQL/WorldDatabase.h"
#include "Implementation/MySQL/HotfixDatabase.h"
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
/// Accessor to the hotfix database
TC_DATABASE_API extern DatabaseWorkerPool<HotfixDatabaseConnection> HotfixDatabase;

#endif
