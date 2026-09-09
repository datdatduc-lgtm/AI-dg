# Projection Verification V2

`projection_verification_v2.py` tạo front X×Z và side/section Y×Z hypothesis từ semantic regions trước khi SketchUp được phép ghi.

Hard checks gồm Build IR READY, overall envelope, bounds X/Y/Z, visible-region set, material targets, dimension hierarchy, evidence của từng view, front vertical coverage và forbidden visible regions.

VN-1 pre-build PASS khi front là 8000×1100, lower `[0,800]`, upper `[800,1100]`, section hierarchy giải thích `750+50+300`, và subregion 50 mm không xuất hiện trong projection nhìn thấy. Post-build verifier dùng cùng contract để so official Ruby read-back.
