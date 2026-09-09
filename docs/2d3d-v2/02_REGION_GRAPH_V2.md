# Region Graph V2

Region Graph V2 là graph spatial riêng, không dùng Material Graph thay thế. Node giữ bounds, state và source refs; edge giữ relationship và evidence.

Các quan hệ embed/recess/slot/offset chỉ được đưa vào graph khi state là `EXPLICIT` hoặc `APPROVED_DERIVED` và có source refs. Quan hệ chưa đủ bằng chứng đi vào `unresolved`, không trở thành geometry.

Trong fixture VN-1, lower body và upper glass là hai region nhìn thấy, liền kề theo Z. Subregion 50 mm nằm trong lower body và chỉ xuất hiện ở section; graph không phát `VISIBLE_IN` cho nó.
