#ifndef THREADSAFE_QUEUE_
#define THREADSAFE_QUEUE_

#include <algorithm>
#include <cassert>
#include <condition_variable>
#include <mutex>
#include <queue>
#include <utility>

// TODO: add reference to book

template <typename T>
class SyncQueue
{
  public:
    SyncQueue()                               = default;
    SyncQueue(const SyncQueue<T>&)            = delete;
    SyncQueue& operator=(const SyncQueue<T>&) = delete;
    SyncQueue(SyncQueue<T>&&)                 = default;
    SyncQueue& operator=(SyncQueue<T>&&)      = default;

    void push(T&& new_item)
    {
        std::lock_guard<std::mutex> lk(m_);
        queue_.push(std::forward<T>(new_item));
        c_.notify_one();
    }

    // waits until an item is available.
    void waitAndPop(T& item)
    {
        std::unique_lock<std::mutex> lk(m_);
        c_.wait(lk, [this]() { return !queue_.empty(); });
        item = std::move(queue_.front());
        queue_.pop();
    }

    std::shared_ptr<T> waitAndPop()
    {
        T item;
        waitAndPop(item);
        return std::make_shared<T>(item);
    }

    // try to put value into item immediatly, and return true if it worked.
    // otherwise false.
    bool tryPop(T& item)
    {
        std::lock_guard<std::mutex> lk(m_);
        if (!queue_.empty()) {
            item = std::move(queue_.front());
            queue_.pop();
            return true;
        }
        return false;
    }

    std::shared_ptr<T> tryPop()
    {
        T item;
        if (tryPop(item)) {
            return std::make_shared<T>(item);
        }
    }

    bool empty() const
    {
        std::lock_guard<std::mutex> lk(m_);
        return queue_.empty();
    }

  private:
    // mutable mutex for const empty method
    mutable std::mutex m_;
    std::condition_variable c_;
    std::queue<T> queue_;
};

class PrngDevSim
{
  public:
    PrngDevSim(SyncQueue<bool>& fifo_queue) : prng_fifo_(fifo_queue)
    {
    }

    void startContGen()
    {
        // create thread
        // start loop
    }

  private:
    static constexpr int access_cycle_cost = 3;

    void logPrngCycles()
    {
        ++nr_access_cycles;
    }

    SyncQueue<bool>& prng_fifo_;

    size_t nr_access_cycles = 0;

    bool stop = true;
};

#endif
