/**
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors
 */

#include "DBUpdater.h"
#include "BuiltInConfig.h"
#include "Config.h"
#include "DatabaseEnv.h"
#include "DatabaseLoader.h"
#include "GitRevision.h"
#include "Log.h"
#include "QueryResult.h"
#include "StartProcess.h"
#include "UpdateFetcher.h"
#include "Transaction.h"
#ifdef WITH_POSTGRESQL
#include "Implementation/PostgreSQL/LoginDatabase.h"
#include "Implementation/PostgreSQL/WorldDatabase.h"
#include "Implementation/PostgreSQL/CharacterDatabase.h"
#include "StringFormat.h"
#include <libpq-fe.h>
#else
#include "Implementation/LoginDatabase.h"
#include "Implementation/WorldDatabase.h"
#include "Implementation/CharacterDatabase.h"
#endif
#include <boost/filesystem/operations.hpp>
#include <fstream>
#include <iostream>
#include <sstream>

std::string DBUpdaterUtil::GetCorrectedMySQLExecutable()
{
#ifdef WITH_POSTGRESQL
    // PostgreSQL doesn't use an external executable for updates
    return "";
#else
    if (!corrected_path().empty())
        return corrected_path();
    else
        return BuiltInConfig::GetMySQLExecutable();
#endif
}

bool DBUpdaterUtil::CheckExecutable()
{
#ifdef WITH_POSTGRESQL
    // PostgreSQL doesn't use an external executable for updates
    // Updates are handled through libpq directly
    return true;
#else
    boost::filesystem::path exe(GetCorrectedMySQLExecutable());
    if (!is_regular_file(exe))
    {
        exe = Trinity::SearchExecutableInPath("mysql");
        if (!exe.empty() && is_regular_file(exe))
        {
            // Correct the path to the cli
            corrected_path() = absolute(exe).generic_string();
            return true;
        }

        TC_LOG_FATAL("sql.updates", "Didn't find any executable MySQL binary at \'{}\' or in path, correct the path in the *.conf (\"MySQLExecutable\").",
            absolute(exe).generic_string());

        return false;
    }
    return true;
#endif
}

std::string& DBUpdaterUtil::corrected_path()
{
    static std::string path;
    return path;
}

// Template specializations
#ifdef WITH_POSTGRESQL
// PostgreSQL Auth Database
template<>
std::string DBUpdater<PostgreSQLLoginDatabaseConnection>::GetConfigEntry()
{
    return "Updates.Auth";
}

template<>
std::string DBUpdater<PostgreSQLLoginDatabaseConnection>::GetTableName()
{
    return "Auth";
}

template<>
std::string DBUpdater<PostgreSQLLoginDatabaseConnection>::GetBaseFile()
{
    return BuiltInConfig::GetSourceDirectory() +
        "/sql/base/postgresql/auth_database.sql";
}

template<>
bool DBUpdater<PostgreSQLLoginDatabaseConnection>::IsEnabled(uint32 const updateMask)
{
    return (updateMask & DatabaseLoader::DATABASE_LOGIN) ? true : false;
}

// PostgreSQL World Database
template<>
std::string DBUpdater<PostgreSQLWorldDatabaseConnection>::GetConfigEntry()
{
    return "Updates.World";
}

template<>
std::string DBUpdater<PostgreSQLWorldDatabaseConnection>::GetTableName()
{
    return "World";
}

template<>
std::string DBUpdater<PostgreSQLWorldDatabaseConnection>::GetBaseFile()
{
    // For PostgreSQL, use the converted world database in postgresql subdirectory
    // The TDB dump should be converted and placed there manually
    return BuiltInConfig::GetSourceDirectory() +
        "/sql/base/postgresql/TDB_full_world_335.sql";
}

template<>
bool DBUpdater<PostgreSQLWorldDatabaseConnection>::IsEnabled(uint32 const updateMask)
{
    return (updateMask & DatabaseLoader::DATABASE_WORLD) ? true : false;
}

template<>
BaseLocation DBUpdater<PostgreSQLWorldDatabaseConnection>::GetBaseLocationType()
{
    return LOCATION_REPOSITORY;
}

// PostgreSQL Character Database
template<>
std::string DBUpdater<PostgreSQLCharacterDatabaseConnection>::GetConfigEntry()
{
    return "Updates.Character";
}

template<>
std::string DBUpdater<PostgreSQLCharacterDatabaseConnection>::GetTableName()
{
    return "Character";
}

template<>
std::string DBUpdater<PostgreSQLCharacterDatabaseConnection>::GetBaseFile()
{
    return BuiltInConfig::GetSourceDirectory() +
        "/sql/base/postgresql/characters_database.sql";
}

template<>
bool DBUpdater<PostgreSQLCharacterDatabaseConnection>::IsEnabled(uint32 const updateMask)
{
    return (updateMask & DatabaseLoader::DATABASE_CHARACTER) ? true : false;
}

#else
// Auth Database
template<>
std::string DBUpdater<LoginDatabaseConnection>::GetConfigEntry()
{
    return "Updates.Auth";
}

template<>
std::string DBUpdater<LoginDatabaseConnection>::GetTableName()
{
    return "Auth";
}

template<>
std::string DBUpdater<LoginDatabaseConnection>::GetBaseFile()
{
    return BuiltInConfig::GetSourceDirectory() +
        "/sql/base/auth_database.sql";
}

template<>
bool DBUpdater<LoginDatabaseConnection>::IsEnabled(uint32 const updateMask)
{
    // This way silences warnings under msvc
    return (updateMask & DatabaseLoader::DATABASE_LOGIN) ? true : false;
}

// World Database
template<>
std::string DBUpdater<WorldDatabaseConnection>::GetConfigEntry()
{
    return "Updates.World";
}

template<>
std::string DBUpdater<WorldDatabaseConnection>::GetTableName()
{
    return "World";
}

template<>
std::string DBUpdater<WorldDatabaseConnection>::GetBaseFile()
{
    return GitRevision::GetFullDatabase();
}

template<>
bool DBUpdater<WorldDatabaseConnection>::IsEnabled(uint32 const updateMask)
{
    // This way silences warnings under msvc
    return (updateMask & DatabaseLoader::DATABASE_WORLD) ? true : false;
}

template<>
BaseLocation DBUpdater<WorldDatabaseConnection>::GetBaseLocationType()
{
    return LOCATION_DOWNLOAD;
}

// Character Database
template<>
std::string DBUpdater<CharacterDatabaseConnection>::GetConfigEntry()
{
    return "Updates.Character";
}

template<>
std::string DBUpdater<CharacterDatabaseConnection>::GetTableName()
{
    return "Character";
}

template<>
std::string DBUpdater<CharacterDatabaseConnection>::GetBaseFile()
{
    return BuiltInConfig::GetSourceDirectory() +
        "/sql/base/characters_database.sql";
}

template<>
bool DBUpdater<CharacterDatabaseConnection>::IsEnabled(uint32 const updateMask)
{
    // This way silences warnings under msvc
    return (updateMask & DatabaseLoader::DATABASE_CHARACTER) ? true : false;
}
#endif  // End of MySQL-specific template specializations

// All
template<class T>
BaseLocation DBUpdater<T>::GetBaseLocationType()
{
    return LOCATION_REPOSITORY;
}

template<class T>
bool DBUpdater<T>::Create(DatabaseWorkerPool<T>& pool)
{
    TC_LOG_INFO("sql.updates", "Database \"{}\" does not exist, do you want to create it? [yes (default) / no]: ",
        pool.GetConnectionInfo()->database);

    std::string answer;
    std::getline(std::cin, answer);
    if (!answer.empty() && !(answer.substr(0, 1) == "y"))
        return false;

    TC_LOG_INFO("sql.updates", "Creating database \"{}\"...", pool.GetConnectionInfo()->database);

#ifdef WITH_POSTGRESQL
    // For PostgreSQL, use libpq directly to create the database
    // We can't use the pool connection because it tries to connect to a non-existent database

    // Build connection string to connect to 'postgres' database
    std::stringstream connStr;
    connStr << "host=" << pool.GetConnectionInfo()->host
            << " port=" << pool.GetConnectionInfo()->port_or_socket
            << " dbname=postgres"  // Connect to default postgres database
            << " user=" << pool.GetConnectionInfo()->user
            << " password=" << pool.GetConnectionInfo()->password
            << " connect_timeout=10"
            << " client_encoding=UTF8";

    PGconn* conn = PQconnectdb(connStr.str().c_str());

    if (PQstatus(conn) != CONNECTION_OK)
    {
        TC_LOG_FATAL("sql.updates", "Failed to connect to PostgreSQL server to create database: {}",
            PQerrorMessage(conn));
        PQfinish(conn);
        return false;
    }

    // Create the database
    // Use template0 to avoid collation conflicts with template1
    std::string createQuery = Trinity::StringFormat(
        "CREATE DATABASE \"{}\" WITH TEMPLATE = template0 ENCODING = 'UTF8' LC_COLLATE = 'C' LC_CTYPE = 'C'",
        pool.GetConnectionInfo()->database);

    PGresult* result = PQexec(conn, createQuery.c_str());
    ExecStatusType status = PQresultStatus(result);
    bool success = (status == PGRES_COMMAND_OK);

    if (!success)
    {
        TC_LOG_FATAL("sql.updates", "Failed to create database {}: {}",
            pool.GetConnectionInfo()->database, PQresultErrorMessage(result));
        PQclear(result);
        PQfinish(conn);
        return false;
    }

    PQclear(result);
    PQfinish(conn);

    TC_LOG_INFO("sql.updates", "Done.");
    return true;
#else
    // Path of temp file
    static Path const temp("create_table.sql");

    // Create temporary query to use external MySQL CLi
    std::ofstream file(temp.generic_string());
    if (!file.is_open())
    {
        TC_LOG_FATAL("sql.updates", "Failed to create temporary query file \"{}\"!", temp.generic_string());
        return false;
    }

    file << "CREATE DATABASE `" << pool.GetConnectionInfo()->database << "` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci\n\n";

    file.close();

    try
    {
        DBUpdater<T>::ApplyFile(pool, pool.GetConnectionInfo()->host, pool.GetConnectionInfo()->user, pool.GetConnectionInfo()->password,
            pool.GetConnectionInfo()->port_or_socket, "", pool.GetConnectionInfo()->ssl, temp);
    }
    catch (UpdateException&)
    {
        TC_LOG_FATAL("sql.updates", "Failed to create database {}! Does the user (named in *.conf) have `CREATE`, `ALTER`, `DROP`, `INSERT` and `DELETE` privileges on the database server?", pool.GetConnectionInfo()->database);
        boost::filesystem::remove(temp);
        return false;
    }

    TC_LOG_INFO("sql.updates", "Done.");
    boost::filesystem::remove(temp);
    return true;
#endif
}

template<class T>
bool DBUpdater<T>::Update(DatabaseWorkerPool<T>& pool)
{
    if (!DBUpdaterUtil::CheckExecutable())
        return false;

    TC_LOG_INFO("sql.updates", "Updating {} database...", DBUpdater<T>::GetTableName());

    Path const sourceDirectory(BuiltInConfig::GetSourceDirectory());

    if (!is_directory(sourceDirectory))
    {
        TC_LOG_ERROR("sql.updates", "DBUpdater: The given source directory {} does not exist, change the path to the directory where your sql directory exists (for example c:\\source\\trinitycore). Shutting down.", sourceDirectory.generic_string());
        return false;
    }

    UpdateFetcher updateFetcher(sourceDirectory, [&](std::string const& query) { DBUpdater<T>::Apply(pool, query); },
        [&](Path const& file) { DBUpdater<T>::ApplyFile(pool, file); },
            [&](std::string const& query) -> QueryResult { return DBUpdater<T>::Retrieve(pool, query); });

    UpdateResult result;
    try
    {
        result = updateFetcher.Update(
            sConfigMgr->GetBoolDefault("Updates.Redundancy", true),
            sConfigMgr->GetBoolDefault("Updates.AllowRehash", true),
            sConfigMgr->GetBoolDefault("Updates.ArchivedRedundancy", false),
            sConfigMgr->GetIntDefault("Updates.CleanDeadRefMaxCount", 3));
    }
    catch (UpdateException&)
    {
        return false;
    }

    std::string const info = Trinity::StringFormat("Containing {} new and {} archived updates.",
        result.recent, result.archived);

    if (!result.updated)
        TC_LOG_INFO("sql.updates", ">> {} database is up-to-date! {}", DBUpdater<T>::GetTableName(), info);
    else
        TC_LOG_INFO("sql.updates", ">> Applied {} {}. {}", result.updated, result.updated == 1 ? "query" : "queries", info);

    return true;
}

template<class T>
bool DBUpdater<T>::Populate(DatabaseWorkerPool<T>& pool)
{
    {
#ifdef WITH_POSTGRESQL
        QueryResult const result = Retrieve(pool, "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'");
#else
        QueryResult const result = Retrieve(pool, "SHOW TABLES");
#endif
        if (result && (result->GetRowCount() > 0))
            return true;
    }

    if (!DBUpdaterUtil::CheckExecutable())
        return false;

    TC_LOG_INFO("sql.updates", "Database {} is empty, auto populating it...", DBUpdater<T>::GetTableName());

    std::string const p = DBUpdater<T>::GetBaseFile();
    if (p.empty())
    {
        TC_LOG_INFO("sql.updates", ">> No base file provided, skipped!");
        return true;
    }

    Path const base(p);
    if (!exists(base))
    {
        switch (DBUpdater<T>::GetBaseLocationType())
        {
            case LOCATION_REPOSITORY:
            {
                TC_LOG_ERROR("sql.updates", ">> Base file \"{}\" is missing. Try fixing it by cloning the source again.",
                    base.generic_string());

                break;
            }
            case LOCATION_DOWNLOAD:
            {
                std::string const filename = base.filename().generic_string();
                std::string const workdir = boost::filesystem::current_path().generic_string();
                TC_LOG_ERROR("sql.updates", ">> File \"{}\" is missing, download it from \"https://github.com/TrinityCore/TrinityCore/releases\"" \
                    " uncompress it and place the file \"{}\" in the directory \"{}\".", filename, filename, workdir);
                break;
            }
        }
        return false;
    }

    // Update database
    TC_LOG_INFO("sql.updates", ">> Applying \'{}\'...", base.generic_string());
    try
    {
        ApplyFile(pool, base);
    }
    catch (UpdateException&)
    {
        return false;
    }

    TC_LOG_INFO("sql.updates", ">> Done!");
    return true;
}

template<class T>
QueryResult DBUpdater<T>::Retrieve(DatabaseWorkerPool<T>& pool, std::string const& query)
{
    return pool.Query(query.c_str());
}

template<class T>
void DBUpdater<T>::Apply(DatabaseWorkerPool<T>& pool, std::string const& query)
{
    pool.DirectExecute(query.c_str());
}

template<class T>
void DBUpdater<T>::ApplyFile(DatabaseWorkerPool<T>& pool, Path const& path)
{
    DBUpdater<T>::ApplyFile(pool, pool.GetConnectionInfo()->host, pool.GetConnectionInfo()->user, pool.GetConnectionInfo()->password,
        pool.GetConnectionInfo()->port_or_socket, pool.GetConnectionInfo()->database, pool.GetConnectionInfo()->ssl, path);
}

template<class T>
void DBUpdater<T>::ApplyFile(DatabaseWorkerPool<T>& pool, [[maybe_unused]] std::string const& host, [[maybe_unused]] std::string const& user,
    [[maybe_unused]] std::string const& password, [[maybe_unused]] std::string const& port_or_socket, std::string const& database, [[maybe_unused]] std::string const& ssl,
    Path const& path)
{
#ifdef WITH_POSTGRESQL
    // PostgreSQL: Apply file directly through connection instead of external tool
    TC_LOG_INFO("sql.updates", "Applying update \"{}\" to database \"{}\"...", path.filename().generic_string(), database);

    try
    {
        // Read the SQL file
        std::ifstream sqlFile(path.generic_string());
        if (!sqlFile.is_open())
        {
            TC_LOG_ERROR("sql.updates", "Failed to open SQL file: {}", path.generic_string());
            throw UpdateException("Failed to open SQL file");
        }

        std::stringstream buffer;
        buffer << sqlFile.rdbuf();
        std::string sql = buffer.str();
        sqlFile.close();

        // PostgreSQL: Execute the file content directly since we can't use SOURCE command
        // For simplicity, just execute the entire file content as one statement
        // PostgreSQL's PQexec can handle multiple statements in one call
        TC_LOG_DEBUG("sql.updates", "Executing SQL file with {} bytes", sql.length());
        pool.DirectExecute(sql.c_str());

        TC_LOG_INFO("sql.updates", "Applied update \"{}\" successfully", path.filename().generic_string());
    }
    catch (std::exception const& e)
    {
        TC_LOG_FATAL("sql.updates", "Applying of file \'{}\' to database \'{}\' failed: {}" \
            " If you are a user, please pull the latest revision from the repository. "
            "Also make sure you have not applied any of the databases with your sql client. "
            "You cannot use auto-update system and import sql files from TrinityCore repository with your sql client. "
            "If you are a developer, please fix your sql query.",
            path.generic_string(), database, e.what());

        throw UpdateException("update failed");
    }
#else
    // MySQL: Use external mysql executable
    std::vector<std::string> args;
    args.reserve(9);

    // CLI Client connection info
    args.emplace_back("-h" + host);
    args.emplace_back("-u" + user);

    if (!password.empty())
        args.emplace_back("-p" + password);

    // Check if we want to connect through ip or socket (Unix only)
#ifdef _WIN32

    if (host == ".")
        args.emplace_back("--protocol=PIPE");
    else
        args.emplace_back("-P" + port_or_socket);

#else

    if (!std::isdigit(port_or_socket[0]))
    {
        // We can't check if host == "." here, because it is named localhost if socket option is enabled
        args.emplace_back("-P0");
        args.emplace_back("--protocol=SOCKET");
        args.emplace_back("-S" + port_or_socket);
    }
    else
        // generic case
        args.emplace_back("-P" + port_or_socket);

#endif

    // Set the default charset to utf8
    args.emplace_back("--default-character-set=utf8mb4");

    // Set max allowed packet to 1 GB
    args.emplace_back("--max-allowed-packet=1GB");

#if !defined(MARIADB_VERSION_ID) && MYSQL_VERSION_ID >= 80000

    if (ssl == "ssl")
        args.emplace_back("--ssl-mode=REQUIRED");

#if MYSQL_VERSION_ID >= 90400

    // Since MySQL 9.4 command line client commands are disabled by default
    // We need to enable them to use `SOURCE` command
    args.emplace_back("--commands=ON");

#endif

#else

    if (ssl == "ssl")
        args.emplace_back("--ssl");

#endif

    // Execute sql file
    args.emplace_back("-e");
    args.emplace_back(Trinity::StringFormat("BEGIN; SOURCE {}; COMMIT;", path.generic_string()));

    // Database
    if (!database.empty())
        args.emplace_back(database);

    // Invokes a mysql process which doesn't leak credentials to logs
    int32 const ret = Trinity::StartProcess(DBUpdaterUtil::GetCorrectedMySQLExecutable(), std::move(args),
                                 "sql.updates", "", true);

    if (ret != EXIT_SUCCESS)
    {
        TC_LOG_FATAL("sql.updates", "Applying of file \'{}\' to database \'{}\' failed!" \
            " If you are a user, please pull the latest revision from the repository. "
            "Also make sure you have not applied any of the databases with your sql client. "
            "You cannot use auto-update system and import sql files from TrinityCore repository with your sql client. "
            "If you are a developer, please fix your sql query.",
            path.generic_string(), pool.GetConnectionInfo()->database);

        throw UpdateException("update failed");
    }
#endif
}

#ifdef WITH_POSTGRESQL
template class TC_DATABASE_API DBUpdater<PostgreSQLLoginDatabaseConnection>;
template class TC_DATABASE_API DBUpdater<PostgreSQLWorldDatabaseConnection>;
template class TC_DATABASE_API DBUpdater<PostgreSQLCharacterDatabaseConnection>;
#else
template class TC_DATABASE_API DBUpdater<LoginDatabaseConnection>;
template class TC_DATABASE_API DBUpdater<WorldDatabaseConnection>;
template class TC_DATABASE_API DBUpdater<CharacterDatabaseConnection>;
#endif
