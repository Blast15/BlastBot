# BlastBot contributor instructions

Các quy tắc trong file này áp dụng cho toàn bộ repository và phải được tuân thủ bởi bot hoặc
agent thực hiện thay đổi source.

## Version bắt buộc cho mọi commit

BlastBot sử dụng Semantic Versioning theo định dạng `MAJOR.MINOR.PATCH`. Version chính thức duy
nhất nằm trong biến `__version__` tại `blastbot/__init__.py`.

Trước khi tạo bất kỳ commit nào:

1. Đọc version hiện tại trong `blastbot/__init__.py`.
2. Phân loại toàn bộ thay đổi của commit theo mức cao nhất bên dưới.
3. Tăng version đúng một lần và đặt các thành phần thấp hơn về `0` khi cần.
4. Cập nhật dòng **Phiên bản hiện tại** trong `README.md` cho khớp hoàn toàn.
5. Chạy `python -m compileall -q blastbot main.py` và `git diff --check`.
6. Không được commit nếu version trong code và README khác nhau.

Quy tắc tăng version:

- `PATCH`: sửa lỗi nhỏ, tài liệu, test, dependency patch hoặc refactor nội bộ tương thích ngược.
  Ví dụ: `2.1.0` thành `2.1.1`.
- `MINOR`: thêm tính năng, command, module hoặc thay đổi hành vi lớn nhưng vẫn tương thích ngược.
  Ví dụ: `2.1.1` thành `2.2.0`.
- `MAJOR`: xây dựng lại kiến trúc, xóa hoặc đổi interface/command/config theo cách phá vỡ tương
  thích. Ví dụ: `2.2.0` thành `3.0.0`.

Nếu một commit chứa nhiều loại thay đổi, luôn dùng mức tăng cao nhất. Không tạo commit mà không
tăng version, kể cả commit chỉ thay đổi tài liệu. Commit message nên dùng Conventional Commits;
`fix` thường là PATCH, `feat` thường là MINOR, và breaking change (`!` hoặc `BREAKING CHANGE`)
phải là MAJOR.

## Đồng bộ hiển thị

Không hard-code version mới ở nơi khác. Code cần hiển thị version phải import
`blastbot.__version__`. README là bản sao phục vụ người đọc và phải được cập nhật trong cùng
commit với `blastbot/__init__.py`.
