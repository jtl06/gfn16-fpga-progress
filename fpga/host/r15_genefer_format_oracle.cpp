// Original test driver; upstream included headers retain their MIT notices.
// Source-pinned genefer22 gint/file format oracle only, not full PL generation.
#include "gint.h"

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    file output(argv[1], "wb", true);
    int version = 1, depth = 2;
    output.write(reinterpret_cast<const char *>(&version), sizeof(version));
    output.write(reinterpret_cast<const char *>(&depth), sizeof(depth));
    for (int value : {1, 2, -1}) {
        gint number(32, 10);
        for (size_t i=0; i<32; ++i) number.data()[i] = i==0 ? value : 0;
        number.reset();
        number.write(output);
        std::cout << number.gethash64() << " " << number.gethash32() << "\n";
    }
    output.write_crc32();
    return 0;
}
