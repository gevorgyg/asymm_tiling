#include <fstream>
#include <iostream>
#include <random>
#include <vector>

template <typename T>
class Matrix
{
  public:
    enum mat_type {
        sparse,
        dense,
    };

    Matrix(size_t n) : elems_(n * n), width_(n), height_(n), nr_elems_(n * n)
    {
    }

    Matrix(size_t n, size_t m)
        : elems_(n * m), width_(n), height_(m), nr_elems_(n * m)
    {
    }

    Matrix(size_t n, mat_type t)
        : elems_(n * n), width_(n), height_(n), nr_elems_(n * n)
    {
        fill(t);
    }

    Matrix(size_t n, size_t m, mat_type t)
        : elems_(n * m), width_(n), height_(m), nr_elems_(n * m)
    {
        fill(t);
    }

    const T& getElem(size_t row, size_t col) const
    {
        return (elems_[row * width_ + col]);
    }

    T& getElem(size_t row, size_t col)
    {
        return (elems_[row * width_ + col]);
    }

    friend std::ostream& operator<<(std::ostream& os, const Matrix<T>& m)
    {
        size_t counter = 0;
        for (const auto& elem : m.elems_) {
            os << elem;
            if (counter % m.width_ == 0) {
                os << std::endl;
            } else {
                os << ' ';
            }
            ++counter;
        }

        return os;
    }

  private:
    std::vector<T> elems_;
    size_t width_;
    size_t height_;
    size_t nr_elems_;

    void fill(mat_type t)
    {
        // generates numbers between 0 to 2^32
        std::mt19937 prng_eng_{std::random_device()()};

        switch (t) {
        case sparse: {
            std::mt19937 to_put_eng_{std::random_device()()};

            size_t treshold = nr_elems_ >> 5;
            if (!nr_elems_) {
                nr_elems_ = 1;
            }

            for (int i = 0; i < nr_elems_; ++i) {
                int to_put = to_put_eng_() % nr_elems_;
                if (to_put < treshold) { // put in a number
                    elems_[i] = prng_eng_();
                }
            }
            break;
        }
        case dense: {
            for (int i = 0; i < nr_elems_; ++i) {
                elems_[i] = prng_eng_();
            }
            break;
        }
        }
    }
};

int main()
{
    Matrix<int> mat(1000, Matrix<int>::sparse);

    std::ofstream ofs("./mat.out");
    ofs << mat;

    return 0;
}
