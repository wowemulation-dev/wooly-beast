/**
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors
 */

#include "Define.h"
#include "Errors.h"
#include "Field.h"
#include "Log.h"
#ifdef WITH_POSTGRESQL
#include "PostgreSQL/PostgreSQLConnection.h"
#else
#include "MySQLConnection.h"
#endif
#include "PreparedStatement.h"
#include "QueryResult.h"
#include "SQLOperation.h"
#include "Transaction.h"
#ifdef _WIN32 // hack for broken mysql.h not including the correct winsock header for SOCKET definition, fixed in 5.7
#include <winsock2.h>
#endif
#ifndef WITH_POSTGRESQL
#include <mysql.h>
#endif
#include <string>
#include <vector>
