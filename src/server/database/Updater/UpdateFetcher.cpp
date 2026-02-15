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

#include "UpdateFetcher.h"
#include "CryptoHash.h"
#include "DBUpdater.h"
#include "Field.h"
#include "Log.h"
#include "QueryResult.h"
#include "Util.h"
#include <boost/filesystem/directory.hpp>
#include <boost/filesystem/operations.hpp>
#include <fstream>
#include <sstream>

using namespace boost::filesystem;

struct UpdateFetcher::DirectoryEntry
{
    DirectoryEntry(Path const& path_, State state_) : path(path_), state(state_) { }

    Path const path;
    State const state;
};

UpdateFetcher::UpdateFetcher(Path const& sourceDirectory,
    std::function<void(std::string const&)> const& apply,
    std::function<void(Path const& path)> const& applyFile,
    std::function<QueryResult(std::string const&)> const& retrieve) :
        _sourceDirectory(std::make_unique<Path>(sourceDirectory)), _apply(apply), _applyFile(applyFile),
        _retrieve(retrieve)
{
}

UpdateFetcher::~UpdateFetcher()
{
}

UpdateFetcher::LocaleFileStorage UpdateFetcher::GetFileList() const
{
    LocaleFileStorage files;
    DirectoryStorage directories = ReceiveIncludedDirectories();
    for (auto const& entry : directories)
        FillFileListRecursively(entry.path, files, entry.state, 1);

    return files;
}

void UpdateFetcher::FillFileListRecursively(Path const& path, LocaleFileStorage& storage, State const state, uint32 const depth) const
{
    static uint32 const MAX_DEPTH = 10;
    static directory_iterator const end;

    for (directory_iterator itr(path); itr != end; ++itr)
    {
        if (is_directory(itr->path()))
        {
            if (depth < MAX_DEPTH)
            {
#ifndef WITH_POSTGRESQL
                // Skip postgresql subdirectory for MySQL builds
                if (itr->path().filename() == "postgresql")
                    continue;
#endif
                FillFileListRecursively(itr->path(), storage, state, depth + 1);
            }
        }
        else if (itr->path().extension() == ".sql")
        {
#ifdef WITH_POSTGRESQL
            // For PostgreSQL builds, only include SQL files from postgresql subdirectories
            if (itr->path().generic_string().find("/postgresql/") == std::string::npos &&
                itr->path().generic_string().find("\\postgresql\\") == std::string::npos)
                continue;
#endif
            TC_LOG_TRACE("sql.updates", "Added locale file \"{}\".", itr->path().filename().generic_string());

            LocaleFileEntry const entry = { itr->path(), state };

            // Check for doubled filenames
            // Because elements are only compared by their filenames, this is ok
            if (storage.find(entry) != storage.end())
            {
                TC_LOG_FATAL("sql.updates", "Duplicate filename \"{}\" occurred. Because updates are ordered " \
                    "by their filenames, every name needs to be unique!", itr->path().generic_string());

                throw UpdateException("Updating failed, see the log for details.");
            }

            storage.insert(entry);
        }
    }
}

UpdateFetcher::DirectoryStorage UpdateFetcher::ReceiveIncludedDirectories() const
{
    DirectoryStorage directories;

#ifdef WITH_POSTGRESQL
    QueryResult const result = _retrieve("SELECT path, state FROM updates_include");
#else
    QueryResult const result = _retrieve("SELECT `path`, `state` FROM `updates_include`");
#endif

    // Process results if available
    if (result)
    {
        do
        {
            Field* fields = result->Fetch();

            std::string path = fields[0].GetString();
            if (path.substr(0, 1) == "$")
                path = _sourceDirectory->generic_string() + path.substr(1);

            Path const p(path);

            if (!is_directory(p))
            {
                TC_LOG_WARN("sql.updates", "DBUpdater: Given update include directory \"{}\" does not exist, skipped!", p.generic_string());
                continue;
            }

            DirectoryEntry const entry = { p, AppliedFileEntry::StateConvert(fields[1].GetString()) };
            directories.push_back(entry);

            TC_LOG_TRACE("sql.updates", "Added applied file \"{}\" from remote.", p.filename().generic_string());

        } while (result->NextRow());
    }

    // Fallback mechanism: if no directories were found, add default paths
    if (directories.empty())
    {
        TC_LOG_WARN("sql.updates", "No update directories found in updates_include table. Using default paths as fallback.");

        // Determine database name from the table query
        std::string dbName;
#ifdef WITH_POSTGRESQL
        QueryResult dbResult = _retrieve("SELECT current_database()");
#else
        QueryResult dbResult = _retrieve("SELECT DATABASE()");
#endif
        if (dbResult)
        {
            dbName = dbResult->Fetch()[0].GetString();

            // Extract database type (auth, characters, world) from database name
            std::string dbType;
            if (dbName.find("auth") != std::string::npos)
                dbType = "auth";
            else if (dbName.find("characters") != std::string::npos || dbName.find("character") != std::string::npos)
                dbType = "characters";
            else if (dbName.find("world") != std::string::npos)
                dbType = "world";

            if (!dbType.empty())
            {
                // Add default paths based on database type
                // MySQL files stay in original location, PostgreSQL uses postgresql subdirectory
#ifdef WITH_POSTGRESQL
                std::string updatePath = _sourceDirectory->generic_string() + "/sql/updates/" + dbType + "/3.3.5/postgresql";
#else
                std::string updatePath = _sourceDirectory->generic_string() + "/sql/updates/" + dbType + "/3.3.5";
#endif
                std::string customPath = _sourceDirectory->generic_string() + "/sql/custom/" + dbType;

                // Add paths if they exist
                Path p(updatePath);
                if (is_directory(p))
                {
                    directories.push_back({ p, RELEASED });
                    TC_LOG_INFO("sql.updates", "Added default update path: {}", updatePath);
                }

                p = Path(customPath);
                if (is_directory(p))
                {
                    directories.push_back({ p, RELEASED });
                    TC_LOG_INFO("sql.updates", "Added default custom path: {}", customPath);
                }

                // Include archived updates - PostgreSQL uses postgresql/ subdirectory
#ifdef WITH_POSTGRESQL
                std::string archivePath = _sourceDirectory->generic_string() + "/sql/old/3.3.5a/" + dbType + "/postgresql";
#else
                std::string archivePath = _sourceDirectory->generic_string() + "/sql/old/3.3.5a/" + dbType;
#endif
                p = Path(archivePath);
                if (is_directory(p))
                {
                    directories.push_back({ p, ARCHIVED });
                    TC_LOG_INFO("sql.updates", "Added default archive path: {}", archivePath);
                }
            }
        }
    }

    return directories;
}

UpdateFetcher::AppliedFileStorage UpdateFetcher::ReceiveAppliedFiles() const
{
    AppliedFileStorage map;

#ifdef WITH_POSTGRESQL
    QueryResult result = _retrieve("SELECT name, hash, state, EXTRACT(EPOCH FROM timestamp)::bigint AS timestamp FROM updates ORDER BY name ASC");
#else
    QueryResult result = _retrieve("SELECT `name`, `hash`, `state`, UNIX_TIMESTAMP(`timestamp`) FROM `updates` ORDER BY `name` ASC");
#endif
    if (!result)
        return map;

    do
    {
        Field* fields = result->Fetch();

        AppliedFileEntry const entry = { fields[0].GetString(), fields[1].GetString(),
            AppliedFileEntry::StateConvert(fields[2].GetString()), fields[3].GetUInt64() };

        map.insert(std::make_pair(entry.name, entry));
    }
    while (result->NextRow());

    return map;
}

std::string UpdateFetcher::ReadSQLUpdate(boost::filesystem::path const& file) const
{
    std::ifstream in(file.c_str());
    if (!in.is_open())
    {
        TC_LOG_FATAL("sql.updates", "Failed to open the sql update \"{}\" for reading! "
                     "Stopping the server to keep the database integrity, "
                     "try to identify and solve the issue or disable the database updater.",
                     file.generic_string());

        throw UpdateException("Opening the sql update failed!");
    }

    auto update = [&in]  {
        std::ostringstream ss;
        ss << in.rdbuf();
        return ss.str();
    }();

    in.close();
    return update;
}

UpdateResult UpdateFetcher::Update(bool const redundancyChecks,
                                   bool const allowRehash,
                                   bool const archivedRedundancy,
                                   int32 const cleanDeadReferencesMaxCount) const
{
    LocaleFileStorage const available = GetFileList();
    AppliedFileStorage applied = ReceiveAppliedFiles();

    size_t countRecentUpdates = 0;
    size_t countArchivedUpdates = 0;

    // Count updates
    for (auto const& entry : applied)
        if (entry.second.state == RELEASED)
            ++countRecentUpdates;
        else
            ++countArchivedUpdates;

    // Fill hash to name cache
    HashToFileNameStorage hashToName;
    for (auto entry : applied)
        hashToName.insert(std::make_pair(entry.second.hash, entry.first));

    size_t importedUpdates = 0;

    for (auto const& availableQuery : available)
    {
        TC_LOG_DEBUG("sql.updates", "Checking update \"{}\"...", availableQuery.first.filename().generic_string());

        AppliedFileStorage::const_iterator iter = applied.find(availableQuery.first.filename().string());
        if (iter != applied.end())
        {
            // If redundancy is disabled, skip it, because the update is already applied.
            if (!redundancyChecks)
            {
                TC_LOG_DEBUG("sql.updates", ">> Update is already applied, skipping redundancy checks.");
                applied.erase(iter);
                continue;
            }

            // If the update is in an archived directory and is marked as archived in our database, skip redundancy checks (archived updates never change).
            if (!archivedRedundancy && (iter->second.state == ARCHIVED) && (availableQuery.second == ARCHIVED))
            {
                TC_LOG_DEBUG("sql.updates", ">> Update is archived and marked as archived in database, skipping redundancy checks.");
                applied.erase(iter);
                continue;
            }
        }

        // Calculate a Sha1 hash based on query content.
        std::string const hash = ByteArrayToHexStr(Trinity::Crypto::SHA1::GetDigestOf(ReadSQLUpdate(availableQuery.first)));

        UpdateMode mode = MODE_APPLY;

        // Update is not in our applied list
        if (iter == applied.end())
        {
            // Catch renames (different filename, but same hash)
            HashToFileNameStorage::const_iterator const hashIter = hashToName.find(hash);
            if (hashIter != hashToName.end())
            {
                // Check if the original file was removed. If not, we've got a problem.
                LocaleFileStorage::const_iterator localeIter;
                // Push localeIter forward
                for (localeIter = available.begin(); (localeIter != available.end()) &&
                    (localeIter->first.filename().string() != hashIter->second); ++localeIter);

                // Conflict!
                if (localeIter != available.end())
                {
                    TC_LOG_WARN("sql.updates", ">> It seems like the update \"{}\" \'{}\' was renamed, but the old file is still there! " \
                        "Treating it as a new file! (It is probably an unmodified copy of the file \"{}\")",
                            availableQuery.first.filename().string(), hash.substr(0, 7),
                                localeIter->first.filename().string());
                }
                // It is safe to treat the file as renamed here
                else
                {
                    TC_LOG_INFO("sql.updates", ">> Renaming update \"{}\" to \"{}\" \'{}\'.",
                        hashIter->second, availableQuery.first.filename().string(), hash.substr(0, 7));

                    RenameEntry(hashIter->second, availableQuery.first.filename().string());
                    applied.erase(hashIter->second);
                    continue;
                }
            }
            // Apply the update if it was never seen before.
            else
            {
                TC_LOG_INFO("sql.updates", ">> Applying update \"{}\" \'{}\'...",
                    availableQuery.first.filename().string(), hash.substr(0, 7));
            }
        }
        // Rehash the update entry if it exists in our database with an empty hash.
        else if (allowRehash && iter->second.hash.empty())
        {
            mode = MODE_REHASH;

            TC_LOG_INFO("sql.updates", ">> Re-hashing update \"{}\" \'{}\'...", availableQuery.first.filename().string(),
                hash.substr(0, 7));
        }
        else
        {
            // If the hash of the files differs from the one stored in our database, reapply the update (because it changed).
            if (iter->second.hash != hash)
            {
                TC_LOG_INFO("sql.updates", ">> Reapplying update \"{}\" \'{}\' -> \'{}\' (it changed)...", availableQuery.first.filename().string(),
                    iter->second.hash.substr(0, 7), hash.substr(0, 7));
            }
            else
            {
                // If the file wasn't changed and just moved, update its state (if necessary).
                if (iter->second.state != availableQuery.second)
                {
                    TC_LOG_DEBUG("sql.updates", ">> Updating the state of \"{}\" to \'{}\'...",
                        availableQuery.first.filename().string(), AppliedFileEntry::StateConvert(availableQuery.second));

                    UpdateState(availableQuery.first.filename().string(), availableQuery.second);
                }

                TC_LOG_DEBUG("sql.updates", ">> Update is already applied and matches the hash \'{}\'.", hash.substr(0, 7));

                applied.erase(iter);
                continue;
            }
        }

        uint32 speed = 0;
        AppliedFileEntry const file = { availableQuery.first.filename().string(), hash, availableQuery.second, 0 };

        switch (mode)
        {
            case MODE_APPLY:
                speed = Apply(availableQuery.first);
                [[fallthrough]];
            case MODE_REHASH:
                UpdateEntry(file, speed);
                break;
        }

        if (iter != applied.end())
            applied.erase(iter);

        if (mode == MODE_APPLY)
            ++importedUpdates;
    }

    // Cleanup up orphaned entries (if enabled)
    if (!applied.empty())
    {
        bool const doCleanup = (cleanDeadReferencesMaxCount < 0) || (applied.size() <= static_cast<size_t>(cleanDeadReferencesMaxCount));

        // Log the directories that were searched for debugging
        DirectoryStorage searchedDirectories = ReceiveIncludedDirectories();
        TC_LOG_DEBUG("sql.updates", "Searched {} directories for update files:", searchedDirectories.size());
        for (auto const& dir : searchedDirectories)
        {
            TC_LOG_DEBUG("sql.updates", "  - {} (state: {})",
                dir.path.generic_string(),
                dir.state == RELEASED ? "RELEASED" : "ARCHIVED");
        }

        for (auto const& entry : applied)
        {
            TC_LOG_WARN("sql.updates", ">> The file \'{}\' was applied to the database, but is missing in" \
                " your update directory now!", entry.first);

            if (doCleanup)
                TC_LOG_INFO("sql.updates", "Deleting orphaned entry \'{}\'...", entry.first);
        }

        if (doCleanup)
            CleanUp(applied);
        else
        {
            TC_LOG_ERROR("sql.updates", "Cleanup is disabled! There were  {} dirty files applied to your database, " \
                "but they are now missing in your source directory!", applied.size());
        }
    }

    return UpdateResult(importedUpdates, countRecentUpdates, countArchivedUpdates);
}

uint32 UpdateFetcher::Apply(Path const& path) const
{
    using Time = std::chrono::high_resolution_clock;

    // Benchmark query speed
    auto const begin = Time::now();

    // Update database
    _applyFile(path);

    // Return the time it took the query to apply
    return uint32(std::chrono::duration_cast<std::chrono::milliseconds>(Time::now() - begin).count());
}

void UpdateFetcher::UpdateEntry(AppliedFileEntry const& entry, uint32 const speed) const
{
#ifdef WITH_POSTGRESQL
    // PostgreSQL uses INSERT ... ON CONFLICT DO UPDATE
    std::string const update = "INSERT INTO updates (name, hash, state, speed) VALUES ('" +
        entry.name + "', '" + entry.hash + "', '" + entry.GetStateAsString() + "', " + std::to_string(speed) +
        ") ON CONFLICT (name) DO UPDATE SET hash = EXCLUDED.hash, state = EXCLUDED.state, speed = EXCLUDED.speed";
#else
    // MySQL uses REPLACE INTO
    std::string const update = "REPLACE INTO `updates` (`name`, `hash`, `state`, `speed`) VALUES (\"" +
        entry.name + "\", \"" + entry.hash + "\", \'" + entry.GetStateAsString() + "\', " + std::to_string(speed) + ")";
#endif

    // Update database
    _apply(update);
}

void UpdateFetcher::RenameEntry(std::string const& from, std::string const& to) const
{
    // Delete the target if it exists
    {
#ifdef WITH_POSTGRESQL
        std::string const update = "DELETE FROM updates WHERE name='" + to + "'";
#else
        std::string const update = "DELETE FROM `updates` WHERE `name`=\"" + to + "\"";
#endif

        // Update database
        _apply(update);
    }

    // Rename
    {
#ifdef WITH_POSTGRESQL
        std::string const update = "UPDATE updates SET name='" + to + "' WHERE name='" + from + "'";
#else
        std::string const update = "UPDATE `updates` SET `name`=\"" + to + "\" WHERE `name`=\"" + from + "\"";
#endif

        // Update database
        _apply(update);
    }
}

void UpdateFetcher::CleanUp(AppliedFileStorage const& storage) const
{
    if (storage.empty())
        return;

    std::stringstream update;
    size_t remaining = storage.size();

#ifdef WITH_POSTGRESQL
    update << "DELETE FROM updates WHERE name IN(";
#else
    update << "DELETE FROM `updates` WHERE `name` IN(";
#endif

    for (auto const& entry : storage)
    {
#ifdef WITH_POSTGRESQL
        update << "'" << entry.first << "'";
#else
        update << "\"" << entry.first << "\"";
#endif
        if ((--remaining) > 0)
            update << ", ";
    }

    update << ")";

    // Update database
    _apply(update.str());
}

void UpdateFetcher::UpdateState(std::string const& name, State const state) const
{
#ifdef WITH_POSTGRESQL
    std::string const update = "UPDATE updates SET state='" + AppliedFileEntry::StateConvert(state) + "' WHERE name='" + name + "'";
#else
    std::string const update = "UPDATE `updates` SET `state`=\'" + AppliedFileEntry::StateConvert(state) + "\' WHERE `name`=\"" + name + "\"";
#endif

    // Update database
    _apply(update);
}

bool UpdateFetcher::PathCompare::operator()(LocaleFileEntry const& left, LocaleFileEntry const& right) const
{
    return left.first.filename().string() < right.first.filename().string();
}
