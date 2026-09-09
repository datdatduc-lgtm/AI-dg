# ModelSpec V2

ModelSpec V2 được sinh đồng thời từ Geometry Ledger V2 và Region Graph V2. Không có đường V2 nào group theo item+dimension rồi bỏ region.

READY yêu cầu source review APPROVED, envelope X/Y/Z đủ, mọi visible region có bounds X/Y/Z và evidence, material mapping đủ, không còn ambiguity tác động trực tiếp tới geometry. Subregion/detail chỉ dùng để giải thích section được giữ nguyên dù không phải visible build region.

Negative case thiếu Y hoặc chưa review trả `REVIEW_REQUIRED`; không tự điền kích thước.
