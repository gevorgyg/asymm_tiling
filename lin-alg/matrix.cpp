#include <fstream>
#include <iostream>
#include <list>
#include <random>

template <typename T>
class SparseMatrix
{
  public:
    struct element {
        T value;
        size_t row;
        size_t col;
    };

    SparseMatrix(size_t n) : width_(n), height_(n), nr_elems_(n * n)
    {
        fill();
    }

    SparseMatrix(size_t n, size_t m) : width_(n), height_(m), nr_elems_(n * m)
    {
        fill();
    }

    const T& getElem(size_t row, size_t col) const
    {
        element e = elems_[row * width_ + col];
        if (e.row == row && e.col == col) {
            return e.value;
        } else {
            return 0;
        }
    }

    T& getElem(size_t row, size_t col)
    {
        element e = elems_[row * width_ + col];
        if (e.row == row && e.col == col) {
            return e.value;
        } else {
            return 0;
        }
    }

    friend std::ostream& operator<<(std::ostream& os, const SparseMatrix<T>& m)
    {
        size_t counter = 0;
        auto it        = m.elems_.begin();
        size_t row;
        size_t col;
        for (int i = 0; i < m.nr_elems_; ++i) {
            row = i / m.width_;
            col = i % m.width_;

            if (row == it->row && col == it->col) {
                os << it->value;
                ++it;
            } else {
                os << 0;
            }
            if (counter != 0 && counter % m.width_ == 0) {
                os << std::endl;
            } else {
                os << ", ";
            }
            ++counter;
        }

        return os;
    }

  private:
    std::list<element> elems_;
    size_t width_;
    size_t height_;
    size_t nr_elems_;

    void fill()
    {
        std::mt19937 to_put_eng_{std::random_device()()};

        size_t treshold = nr_elems_ >> 8;
        if (!nr_elems_) {
            nr_elems_ = 1;
        }

        for (int i = 0; i < nr_elems_; ++i) {
            int to_put = to_put_eng_() % nr_elems_;
            if (to_put < treshold) { // put in a number
                size_t row = i / width_;
                size_t col = i % width_;
                elems_.push_back({1, row, col});
            }
        }
    }
};

int main()
{
    SparseMatrix<int> mat(10000);

    std::ofstream ofs("./mat.sparse");
    ofs << mat << std::endl;

    return 0;
}
