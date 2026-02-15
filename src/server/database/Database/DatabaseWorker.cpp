/**
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors
 */

#include "DatabaseWorker.h"
#include "SQLOperation.h"
#include "ProducerConsumerQueue.h"

DatabaseWorker::DatabaseWorker(ProducerConsumerQueue<SQLOperation*>* newQueue, DatabaseConnection* connection)
{
    _connection = connection;
    _queue = newQueue;
    _cancelationToken = false;
    _workerThread = std::thread(&DatabaseWorker::WorkerThread, this);
}

DatabaseWorker::~DatabaseWorker()
{
    _cancelationToken = true;

    // Signal shutdown but don't discard pending operations
    _queue->Shutdown();

    _workerThread.join();
}

void DatabaseWorker::WorkerThread()
{
    if (!_queue)
        return;

    for (;;)
    {
        SQLOperation* operation = nullptr;

        _queue->WaitAndPop(operation);

        if (!operation)
        {
            // Woken up with no operation - check if we should drain remaining items
            if (_cancelationToken)
            {
                // Drain any remaining operations before exiting
                while (_queue->Pop(operation))
                {
                    operation->SetConnection(_connection);
                    operation->call();
                    delete operation;
                }
                return;
            }
            // Spurious wakeup, continue waiting
            continue;
        }

        operation->SetConnection(_connection);
        operation->call();

        delete operation;
    }
}
