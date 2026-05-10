#pragma once
/**
 * WavePoint - Thread-Safe Queue
 * 
 * Lock-free SPSC (Single Producer Single Consumer) queue for inter-thread
 * communication. Used to pass data between capture, inference, and injection threads.
 */

#include <array>
#include <atomic>
#include <optional>
#include <cstddef>

namespace gesture_mouse {

/**
 * Lock-free single-producer single-consumer queue.
 * 
 * This queue is designed for the threading model where:
 * - One thread produces data (e.g., camera capture)
 * - One thread consumes data (e.g., inference)
 * 
 * The queue uses atomic operations and is wait-free for both push and pop.
 * If the queue is full, push will overwrite the oldest item (for real-time systems).
 */
template<typename T, size_t Capacity>
class ThreadSafeQueue {
public:
    static_assert(Capacity > 0, "Queue capacity must be positive");
    static_assert((Capacity & (Capacity - 1)) == 0, "Capacity must be power of 2");
    
    ThreadSafeQueue() : head_(0), tail_(0) {}
    
    // Non-copyable, non-movable
    ThreadSafeQueue(const ThreadSafeQueue&) = delete;
    ThreadSafeQueue& operator=(const ThreadSafeQueue&) = delete;
    ThreadSafeQueue(ThreadSafeQueue&&) = delete;
    ThreadSafeQueue& operator=(ThreadSafeQueue&&) = delete;
    
    /**
     * Push an item to the queue.
     * If queue is full, overwrites the oldest item.
     * 
     * @param item Item to push
     * @return true if pushed without overwrite, false if overwrote oldest
     */
    bool push(const T& item) {
        size_t current_tail = tail_.load(std::memory_order_relaxed);
        size_t next_tail = (current_tail + 1) & (Capacity - 1);
        
        // Check if queue is full
        size_t current_head = head_.load(std::memory_order_acquire);
        bool was_full = (next_tail == current_head);
        
        if (was_full) {
            // Overwrite mode: advance head to drop oldest
            head_.store((current_head + 1) & (Capacity - 1), std::memory_order_release);
        }
        
        buffer_[current_tail] = item;
        tail_.store(next_tail, std::memory_order_release);
        
        return !was_full;
    }
    
    /**
     * Push an item using move semantics.
     */
    bool push(T&& item) {
        size_t current_tail = tail_.load(std::memory_order_relaxed);
        size_t next_tail = (current_tail + 1) & (Capacity - 1);
        
        size_t current_head = head_.load(std::memory_order_acquire);
        bool was_full = (next_tail == current_head);
        
        if (was_full) {
            head_.store((current_head + 1) & (Capacity - 1), std::memory_order_release);
        }
        
        buffer_[current_tail] = std::move(item);
        tail_.store(next_tail, std::memory_order_release);
        
        return !was_full;
    }
    
    /**
     * Try to pop an item from the queue.
     * 
     * @return The item if available, std::nullopt if queue is empty
     */
    std::optional<T> pop() {
        size_t current_head = head_.load(std::memory_order_relaxed);
        size_t current_tail = tail_.load(std::memory_order_acquire);
        
        if (current_head == current_tail) {
            return std::nullopt;  // Queue is empty
        }
        
        T item = std::move(buffer_[current_head]);
        head_.store((current_head + 1) & (Capacity - 1), std::memory_order_release);
        
        return item;
    }
    
    /**
     * Peek at the front item without removing it.
     */
    std::optional<T> peek() const {
        size_t current_head = head_.load(std::memory_order_relaxed);
        size_t current_tail = tail_.load(std::memory_order_acquire);
        
        if (current_head == current_tail) {
            return std::nullopt;
        }
        
        return buffer_[current_head];
    }
    
    /**
     * Get the latest item, clearing all older items.
     * Useful when you only care about the most recent data.
     */
    std::optional<T> pop_latest() {
        std::optional<T> latest;
        while (auto item = pop()) {
            latest = std::move(item);
        }
        return latest;
    }
    
    /**
     * Check if the queue is empty.
     */
    bool empty() const {
        return head_.load(std::memory_order_acquire) == 
               tail_.load(std::memory_order_acquire);
    }
    
    /**
     * Get the current number of items in the queue.
     */
    size_t size() const {
        size_t head = head_.load(std::memory_order_acquire);
        size_t tail = tail_.load(std::memory_order_acquire);
        return (tail - head + Capacity) & (Capacity - 1);
    }
    
    /**
     * Clear all items from the queue.
     */
    void clear() {
        head_.store(0, std::memory_order_release);
        tail_.store(0, std::memory_order_release);
    }
    
    /**
     * Get the capacity of the queue.
     */
    constexpr size_t capacity() const {
        return Capacity;
    }

private:
    std::array<T, Capacity> buffer_;
    alignas(64) std::atomic<size_t> head_;  // Cache line aligned
    alignas(64) std::atomic<size_t> tail_;  // Separate cache line
};

/**
 * Multi-producer multi-consumer queue using mutex.
 * Use this when SPSC guarantees cannot be made.
 */
template<typename T, size_t Capacity>
class MPMCQueue {
public:
    MPMCQueue() : head_(0), tail_(0), count_(0) {}
    
    bool push(const T& item) {
        std::lock_guard<std::mutex> lock(mutex_);
        
        if (count_ >= Capacity) {
            // Overwrite oldest
            head_ = (head_ + 1) % Capacity;
            count_--;
        }
        
        buffer_[tail_] = item;
        tail_ = (tail_ + 1) % Capacity;
        count_++;
        
        return true;
    }
    
    std::optional<T> pop() {
        std::lock_guard<std::mutex> lock(mutex_);
        
        if (count_ == 0) {
            return std::nullopt;
        }
        
        T item = std::move(buffer_[head_]);
        head_ = (head_ + 1) % Capacity;
        count_--;
        
        return item;
    }
    
    bool empty() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return count_ == 0;
    }
    
    size_t size() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return count_;
    }
    
    void clear() {
        std::lock_guard<std::mutex> lock(mutex_);
        head_ = 0;
        tail_ = 0;
        count_ = 0;
    }

private:
    std::array<T, Capacity> buffer_;
    size_t head_;
    size_t tail_;
    size_t count_;
    mutable std::mutex mutex_;
};

} // namespace gesture_mouse
