/**
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors
 */

#ifndef _POSTGRESQLFIELD_H
#define _POSTGRESQLFIELD_H

#include "Field.h"
#include <libpq-fe.h>

// PostgreSQLField is currently just a placeholder
// The actual field functionality is provided by the base Field class
// and values are set by the ResultSet classes which are friends of Field
class TC_DATABASE_API PostgreSQLField : public Field
{
public:
    PostgreSQLField() = default;
    ~PostgreSQLField() = default;
};

#endif