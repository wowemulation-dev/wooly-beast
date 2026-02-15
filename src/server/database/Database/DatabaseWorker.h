/**
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors
 */

#ifndef _WORKERTHREAD_H
#define _WORKERTHREAD_H

#include "Define.h"
#include <atomic>
#include <thread>

template <typename T>
class ProducerConsumerQueue;

#ifdef WITH_POSTGRESQL
class PostgreSQLConnection;
typedef PostgreSQLConnection DatabaseConnection;
#else
class MySQLConnection;
typedef MySQLConnection DatabaseConnection;
#endif
class SQLOperation;

class TC_DATABASE_API DatabaseWorker
{
    public:
        DatabaseWorker(ProducerConsumerQueue<SQLOperation*>* newQueue, DatabaseConnection* connection);
        ~DatabaseWorker();

    private:
        ProducerConsumerQueue<SQLOperation*>* _queue;
        DatabaseConnection* _connection;

        void WorkerThread();
        std::thread _workerThread;

        std::atomic<bool> _cancelationToken;

        DatabaseWorker(DatabaseWorker const& right) = delete;
        DatabaseWorker& operator=(DatabaseWorker const& right) = delete;
};

#endif
