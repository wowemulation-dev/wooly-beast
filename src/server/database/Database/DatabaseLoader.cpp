/**
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors
 */

#include "DatabaseLoader.h"
#include "Config.h"
#include "DatabaseEnv.h"
#include "DBUpdater.h"
#include "Log.h"

#ifdef WITH_POSTGRESQL
// PostgreSQL error codes
#define ER_BAD_DB_ERROR 1049  // Database doesn't exist - using MySQL error code for compatibility
#else
#include <mysqld_error.h>
#endif

DatabaseLoader::DatabaseLoader(std::string const& logger, uint32 const defaultUpdateMask)
    : _logger(logger), _autoSetup(sConfigMgr->GetBoolDefault("Updates.AutoSetup", true)),
    _updateFlags(sConfigMgr->GetIntDefault("Updates.EnableDatabases", defaultUpdateMask))
{
}

template <class T>
DatabaseLoader& DatabaseLoader::AddDatabase(DatabaseWorkerPool<T>& pool, std::string const& name)
{
    bool const updatesEnabledForThis = DBUpdater<T>::IsEnabled(_updateFlags);

    _open.push([this, name, updatesEnabledForThis, &pool]() -> bool
    {
        std::string const dbString = sConfigMgr->GetStringDefault(name + "DatabaseInfo", "");
        if (dbString.empty())
        {
            TC_LOG_ERROR(_logger, "Database {} not specified in configuration file!", name);
            return false;
        }

        uint8 const asyncThreads = uint8(sConfigMgr->GetIntDefault(name + "Database.WorkerThreads", 1));
        if (asyncThreads < 1 || asyncThreads > 32)
        {
            TC_LOG_ERROR(_logger, "{} database: invalid number of worker threads specified. "
                "Please pick a value between 1 and 32.", name);
            return false;
        }

        uint8 const synchThreads = uint8(sConfigMgr->GetIntDefault(name + "Database.SynchThreads", 1));

        pool.SetConnectionInfo(dbString, asyncThreads, synchThreads);
        if (uint32 error = pool.Open())
        {
            // Database does not exist
            if ((error == ER_BAD_DB_ERROR) && updatesEnabledForThis && _autoSetup)
            {
                // Try to create the database and connect again if auto setup is enabled
                if (DBUpdater<T>::Create(pool) && (!pool.Open()))
                    error = 0;
            }

            // If the error wasn't handled quit
            if (error)
            {
                TC_LOG_ERROR("sql.driver", "\nDatabasePool {} NOT opened. There were errors opening the MySQL connections. Check your SQLDriverLogFile "
                    "for specific errors. Read wiki at https://www.trinitycore.info", name);

                return false;
            }
        }
        // Add the close operation
        _close.push([&pool]
        {
            pool.Close();
        });
        return true;
    });

    // Populate and update only if updates are enabled for this pool
    if (updatesEnabledForThis)
    {
        _populate.push([this, name, &pool]() -> bool
        {
            if (!DBUpdater<T>::Populate(pool))
            {
                TC_LOG_ERROR(_logger, "Could not populate the {} database, see log for details.", name);
                return false;
            }
            return true;
        });

        _update.push([this, name, &pool]() -> bool
        {
            if (!DBUpdater<T>::Update(pool))
            {
                TC_LOG_ERROR(_logger, "Could not update the {} database, see log for details.", name);
                return false;
            }
            return true;
        });
    }

    _prepare.push([this, name, &pool]() -> bool
    {
        if (!pool.PrepareStatements())
        {
            TC_LOG_ERROR(_logger, "Could not prepare statements of the {} database, see log for details.", name);
            return false;
        }
        return true;
    });

    return *this;
}

bool DatabaseLoader::Load()
{
    if (!_updateFlags)
        TC_LOG_INFO("sql.updates", "Automatic database updates are disabled for all databases!");

    if (!OpenDatabases())
        return false;

    if (!PopulateDatabases())
        return false;

    if (!UpdateDatabases())
        return false;

    if (!PrepareStatements())
        return false;

    return true;
}

bool DatabaseLoader::OpenDatabases()
{
    return Process(_open);
}

bool DatabaseLoader::PopulateDatabases()
{
    return Process(_populate);
}

bool DatabaseLoader::UpdateDatabases()
{
    return Process(_update);
}

bool DatabaseLoader::PrepareStatements()
{
    return Process(_prepare);
}

bool DatabaseLoader::Process(std::queue<Predicate>& queue)
{
    while (!queue.empty())
    {
        if (!queue.front()())
        {
            // Close all open databases which have a registered close operation
            while (!_close.empty())
            {
                _close.top()();
                _close.pop();
            }

            return false;
        }

        queue.pop();
    }
    return true;
}

#ifdef WITH_POSTGRESQL
template TC_DATABASE_API
DatabaseLoader& DatabaseLoader::AddDatabase<PostgreSQLLoginDatabaseConnection>(DatabaseWorkerPool<PostgreSQLLoginDatabaseConnection>&, std::string const&);
template TC_DATABASE_API
DatabaseLoader& DatabaseLoader::AddDatabase<PostgreSQLCharacterDatabaseConnection>(DatabaseWorkerPool<PostgreSQLCharacterDatabaseConnection>&, std::string const&);
template TC_DATABASE_API
DatabaseLoader& DatabaseLoader::AddDatabase<PostgreSQLWorldDatabaseConnection>(DatabaseWorkerPool<PostgreSQLWorldDatabaseConnection>&, std::string const&);
#else
template TC_DATABASE_API
DatabaseLoader& DatabaseLoader::AddDatabase<LoginDatabaseConnection>(DatabaseWorkerPool<LoginDatabaseConnection>&, std::string const&);
template TC_DATABASE_API
DatabaseLoader& DatabaseLoader::AddDatabase<CharacterDatabaseConnection>(DatabaseWorkerPool<CharacterDatabaseConnection>&, std::string const&);
template TC_DATABASE_API
DatabaseLoader& DatabaseLoader::AddDatabase<WorldDatabaseConnection>(DatabaseWorkerPool<WorldDatabaseConnection>&, std::string const&);
#endif
