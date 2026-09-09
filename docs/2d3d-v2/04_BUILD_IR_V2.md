# Build IR V2

Build IR V2 dùng operation `create_item_assembly` và là semantic source of truth. Mỗi operation giữ coordinate frame, envelope, regions/subregions, relationships, material nodes, source refs và verification contract.

Region `VISIBLE` mới có `build_geometry=true`. Region/detail `SECTION_ONLY` vẫn được lưu để verification giải thích hình cắt nhưng không được biến thành một khối nhìn thấy.

Operation ID được tạo deterministically từ run ID + item code. Executor không eval Ruby tùy ý.
