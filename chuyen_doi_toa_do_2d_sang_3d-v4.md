# GIẢI MÃ CHI TIẾT CHUỖI CÔNG THỨC CHUYỂN ĐỔI TỌA ĐỘ ÁNH MẮT 2D SANG KHÔNG GIAN 3D CỦA ROBOT
*(Dành cho người không chuyên - Trực quan, Dễ hiểu, Bản chất Hình học & Không bị lỗi Ký hiệu)*

---

## 💡 LỜI NÓI ĐẦU: BÀI TOÁN "BẤT BỒNG NGÔN NGỮ" GIỮA MẮT VÀ ROBOT

Hãy tưởng tượng bạn đang nhìn vào một chiếc cốc nằm trên bàn và muốn cánh tay robot trợ lý vươn ra gắp chiếc cốc đó giúp bạn.

* **Mắt bạn** nhìn môi trường qua một **mặt cầu con ngươi** và thiết bị đo mắt (Tobii Eye Tracker) chỉ ghi nhận được một **tấm ảnh phẳng 2D** (tọa độ pixel u, v).
* **Cánh tay robot** lại là một khối cơ khí hoạt động trong **thực tế 3D** (chiều ngang X, chiều sâu Y, chiều cao Z tính từ chân đế robot).

Làm thế nào để dịch chuyển một "chấm sáng 2D" trên màn hình thành một "tọa độ 3D thực tế" ngoài đời để robot biết chính xác vị trí vươn tay tới?

Đó chính là nhiệm vụ của **PHẦN 2: CHUỖI 4 CÔNG THỨC CHUYỂN ĐỔI TỌA ĐỘ KHÔNG GIAN**.

```text
 ┌────────────────┐     1. Đa thức 2nd    ┌──────────────────┐
 │ Mắt người nhìn ├──────────────────────►│ Pixel Màn hình   │
 │ (Tín hiệu thô) │                       │ (Tọa độ u, v)    │
 └────────────────┘                       └────────┬─────────┘
                                                   │ 2. Ma trận Intrinsic K
                                                   ▼
 ┌────────────────┐     4. Tsai Hand-Eye  ┌──────────────────┐
 │ Tọa độ Robot 3D│◄──────────────────────┤ Tọa độ Camera 3D │
 │ (X, Y, Z thực) │                       │ (Kết hợp Depth Z)│
 └────────────────┘                       └──────────────────┘
```

---

## 📌 BƯỚC 2.1: QUY ĐỔI TÍN HIỆU MẮT THÔ THÀNH PIXEL MÀN HÌNH
*(Mô hình Nội suy Đa thức Bậc 2 - Second-degree Polynomial Fitting)*

### 1. Công thức Toán học:

```text
┌       ┐     ┌                                   ┐   ┌    ┐
│   u   │     │ a11   a12   a13   a14   a15   a16 │   │ 1  │
│       │  =  │                                   │ * │ x  │
│   v   │     │ a21   a22   a23   a24   a25   a26 │   │ y  │
└       ┘     └                                   ┘   │ x² │
                                                      │ y² │
                                                      │ xy │
                                                      └    ┘
```

---

### 2. Ý nghĩa trực quan & Bản chất vì sao lại làm được?

#### 🎯 Bài toán:
Cảm biến **Tobii Eye Tracker 4c** nằm nghiêng bên dưới màn hình, đo góc xoay con ngươi và trả về cặp số thô (x, y). Màn hình máy tính lại là một khung lưới điểm ảnh phẳng (u, v) có độ phân giải 1920 x 1080 pixel. Hai số (x, y) này không thể dùng trực tiếp vì quả cầu mắt xoay theo đường cong, còn thiết bị lại bị đặt nhìn hắt xéo từ dưới lên.

#### 🧩 Giải mã từng mảnh ghép trong vector [1, x, y, x², y², xy]ᵀ:

* **Thành phần 1 (Dịch gốc tọa độ - Translation)**:
  * *Bản chất*: Điểm (0, 0) của cảm biến Tobii nằm ở góc kính dưới bàn, còn điểm (0, 0) của màn hình nằm ở góc trên bên trái. Hằng số 1 giúp kéo gốc tọa độ từ dưới bàn lên đúng góc màn hình.
* **Thành phần bậc nhất (x, y) (Co giãn & Xoay phẳng - Scaling & Rotation)**:
  * *Bản chất*: Phóng to dải tín hiệu nhỏ của con ngươi thành dải kích thước màn hình (1920 x 1080). Đồng thời, nếu bạn ngồi hơi nghiêng đầu, cặp (x, y) sẽ xoay nhẹ tín hiệu lại cho thẳng.
* **Thành phần bậc hai (x², y²) (Uốn phẳng độ cong quả cầu mắt - Curvature Correction)**:
  * *Bản chất*: Quả cầu mắt xoay theo hình cầu. Khi bạn đảo mắt ra 4 góc mép màn hình, góc xoay con ngươi tăng lên theo đường cong parabol (x², y²). Thành phần này đóng vai trò như **chiếc khuôn uốn** – nó bẻ cong dải tín hiệu bị lồi ở mép để kéo phẳng nó trùng khớp với màn hình.
* **Thành phần chéo (xy) (Nắn hình thang thành hình chữ nhật - Perspective Correction)**:
  * *Bản chất*: Vì kính Tobii đặt ở dưới nhìn hắt xéo lên mắt, không gian quan sát bị méo thành **hình thang** (phía dưới gần cảm biến thì to, phía trên xa thì bị thu hẹp). Thành phần chéo xy tự động nới rộng chiều ngang phía trên ra, nắn khung hình thang thành hình chữ nhật vuông vức.

---

### 3. Ma trận 12 hệ số a_ij ở đâu ra?

Máy tính không tự đoán được 12 số này. Trước khi dùng, bạn phải thực hiện **Quy trình hiệu chuẩn 9 điểm (9-point calibration)**:
1. Màn hình hiện lần lượt **9 điểm đỏ** ở các vị trí cố định. Màn hình đã biết trước tọa độ pixel thực tế (u, v) của 9 điểm này.
2. Bạn nhìn vào từng điểm đỏ, kính Tobii ghi nhận 9 cặp tín hiệu mắt thô (x, y).
3. Máy tính dùng thuật toán **Hồi quy Bình phương Tối thiểu (Least Squares)** để vặn bộ 12 "núm xoay" a11 ... a26 sao cho sai lệch giữa điểm mắt tính ra và điểm đỏ thực tế là nhỏ nhất. Bộ 12 số này sau đó được khóa lại làm "bản đồ chuyển đổi" riêng cho mắt của bạn.

---

## 📌 BƯỚC 2.2: CHUẨN HÓA TỌA ĐỘ PIXEL
*(Camera Intrinsic Normalization)*

### 1. Công thức Toán học:

```text
x_norm = (u - c_x) / f_x
y_norm = (v - c_y) / f_y
```

---

### 2. Ý nghĩa trực quan:

#### 🎯 Bài toán:
Mỗi loại màn hình hay ống kính camera lại có kích thước, độ phân giải và góc nhìn khác nhau (ví dụ: camera góc rộng vs camera góc hẹp). Nếu giữ nguyên tọa độ pixel (u, v), thuật toán sẽ bị phụ thuộc vào từng thiết bị cụ thể.

#### 🧩 Giải mã từng biến số:
* **(u, v)**: Tọa độ pixel trên ảnh màn hình thu được từ Bước 2.1.
* **(c_x, c_y)**: **Tâm quang học (Principal Point)** – điểm chính giữa tâm ống kính camera. Việc trừ đi (c_x, c_y) giúp dời tâm tọa độ về đúng tâm quang học của camera.
* **(f_x, f_y)**: **Tiêu cự camera (Focal Length)** tính bằng đơn vị pixel. Việc chia cho tiêu cự giúp quy đổi kích thước điểm ảnh về góc mở ống kính.
* **(x_norm, y_norm)**: **Tọa độ chuẩn hóa** nằm trên mặt phẳng hình ảnh tiêu chuẩn đặt ở khoảng cách Z = 1 mét trước ống kính.

#### 💡 Bản chất:
Bước này giúp **tách rời tín hiệu khỏi loại camera cụ thể**, quy đổi mọi điểm nhìn về một "chiếc thước đo chuẩn quốc tế" không phụ thuộc vào độ phân giải màn hình.

---

## 📌 BƯỚC 2.3: DỰNG TIA CHIẾU 3D TRONG HỆ TỌA ĐỘ CAMERA
*(Pinhole Camera Ray Projection & Depth Map Association)*

### 1. Công thức Toán học:

```text
                  ┌        ┐   ┌          ┐
                  │ x_norm │   │ X_camera │
P_camera = Z_cam *│ y_norm │ = │ Y_camera │
                  │   1    │   │ Z_camera │
                  └        ┘   └          ┘
```

---

### 2. Ý nghĩa trực quan:

#### 🎯 Bài toán:
Mắt bạn nhìn vào một điểm trên ảnh 2D, nhưng vật thể đó nằm cách camera 50 cm hay 100 cm? Ảnh 2D hoàn toàn không có thông tin chiều sâu.

#### 📸 Camera Độ sâu ZED2 hoạt động ra sao?
Camera ZED2 có 2 ống kính (stereo camera) giống như hai mắt người. Nó trả về một **Bản đồ độ sâu (Depth Map)**. Đây là một tấm lưới 2D đúng bằng kích thước ảnh, nhưng tại ô pixel [v, u], nó lưu một số thực chính là khoảng cách vật lý thực tế Z_camera (tính bằng mét).

#### 🧩 Giải mã công thức:
* **Vector [x_norm, y_norm, 1]ᵀ**: Đại diện cho **hướng của tia la-ze** bắn từ tâm camera đi qua điểm pixel [u, v].
* **Z_camera**: Độ dài của tia la-ze (khoảng cách từ camera đến vật thể).
* **P_camera = [X_c, Y_c, Z_c]ᵀ**: Tọa độ 3D thực tế của vật thể trong không gian lấy **tâm camera ZED2 làm gốc (0,0,0)**.

#### 💡 Bản chất:
Bằng cách nhân hướng nhìn chuẩn hóa với khoảng cách độ sâu Z, ta đã **bắn một tia la-ze từ tâm camera chạm đúng vào bề mặt vật thể trong không gian 3D**.

---

## 📌 BƯỚC 2.4: BIẾN ĐỔI SANG HỆ TỌA ĐỘ CHÂN ĐẾ CÁNH TAY ROBOT
*(Ma trận Hiệu chuẩn Hand-Eye Tsai - Homogeneous Transformation Matrix)*

### 1. Công thức Toán học:

```text
┌          ┐   ┌                             ┐   ┌          ┐
│ X_robot  │   │  R11   R12   R13   t_x      │   │ X_camera │
│ Y_robot  │ = │  R21   R22   R23   t_y      │ * │ Y_camera │
│ Z_robot  │   │  R31   R32   R33   t_z      │   │ Z_camera │
│    1     │   │   0     0     0     1       │   │    1     │
└          ┘   └                             ┘   └          ┘

Viết gọn: P_robotic = T_camera_hand * [P_camera; 1]
```

---

### 2. Giải mã Chi tiết 4 Thành phần trong Ma trận T_camera_hand (4x4):

Ma trận `T_camera_hand` (4x4) đóng vai trò là một **"thông dịch viên địa lý"**, giúp đổi vị trí vật thể từ góc nhìn của đôi mắt camera sang góc nhìn chân đế cơ khí của robot.

#### 🔴 Khối 1: Ma trận Xoay R (3x3) - [Góc trên bên trái, kích thước 3 hàng x 3 cột]
```text
┌                   ┐
│ R11   R12   R13   │
│ R21   R22   R23   │
│ R31   R32   R33   │
└                   ┘
```
* **Ý nghĩa vật lý**: Đại diện cho **góc nghiêng không gian** của Camera ZED2 so với chân đế robot (gồm 3 góc xoay: nghiêng trước-sau *Pitch*, nghiêng trái-phải *Roll*, và xoay hướng *Yaw*).
* **Bản chất**: Camera hiếm khi được kẹp hoàn toàn song song với chân đế robot mà thường bị đặt nghiêng hoặc gật xéo xuống bàn. Khối R (3x3) giúp "nắn" lại hướng nhìn của camera về cùng mặt phẳng quy chiếu chuẩn với chân đế robot.

#### 🟢 Khối 2: Vector Dịch chuyển t (3x1) - [Cột thứ 4, từ hàng 1 đến hàng 3]
```text
┌     ┐
│ t_x │
│ t_y │
│ t_z │
└     ┘
```
* **Ý nghĩa vật lý**: Khoảng cách địa lý thực tế (đơn vị: mét hoặc cm) giữa **Tâm ống kính Camera** và **Tâm chân đế Robot**.
  * **t_x**: Camera nằm lệch sang trái (-) hay sang phải (+) bao nhiêu cm so với gốc đế robot.
  * **t_y**: Camera nằm ở phía trước (+) hay phía sau (-) bao nhiêu cm so với gốc đế robot.
  * **t_z**: Camera nằm cao (+) hay thấp (-) bao nhiêu cm so với gốc đế robot.

#### 🔵 Khối 3: Hàng Tọa độ Đồng nhất [0, 0, 0, 1] - [Hàng thứ 4 dưới cùng]
```text
┌                 ┐
│  0   0   0   1  │
└                 ┘
```
* **Bản chất toán học**: Trong không gian 3D, một vị trí thực tế chỉ cần 3 số (X, Y, Z). Tuy nhiên, nếu dùng ma trận 3x3, toán học bắt buộc phải chia làm 2 phép tính rời rạc: `P_robot = R * P_camera + t` (quay góc trước, rồi mới cộng độ dịch).
* **Tại sao cần hàng [0, 0, 0, 1]?**: Việc thêm hàng `[0, 0, 0, 1]` biến ma trận thành kích thước 4x4, cho phép **gộp cả phép quay R và phép dịch t vào duy nhất 1 phép nhân ma trận**.
  * Ba số **0, 0, 0** đảm bảo không làm biến dạng hay co giãn tỉ lệ không gian.
  * Số **1** ở cuối giữ cho vector kết quả luôn có đuôi là 1, sẵn sàng cho các phép tính tiếp theo.
  * **Hiệu quả**: Phép nhân 4x4 duy nhất này giúp rút ngắn thời gian tính toán xuống chỉ còn **2.97 miligiây**, đạt tốc độ phản hồi thời gian thực!

---

### 3. Công thức Khai triển Phương trình Đại số theo từng Trục:

Khi nhân ma trận 4x4 ở trên ra phương trình đại số thực tế, ta thu được tọa độ gắp 3D của robot như sau:

* **Trục ngang X**: `X_robot = (R11 * X_c + R12 * Y_c + R13 * Z_c) + t_x`
* **Trục sâu Y**: `Y_robot = (R21 * X_c + R22 * Y_c + R23 * Z_c) + t_y`
* **Trục cao Z**: `Z_robot = (R31 * X_c + R32 * Y_c + R33 * Z_c) + t_z`

👉 *Trong đó, phần đóng ngoặc `(...)` thực hiện quay góc nghiêng camera, còn phần `+ t` thực hiện cộng khoảng cách dịch chuyển giữa camera và robot.*

---

## 🔄 TÓM TẮT DÒNG CHẢY DỮ LIỆU BẰNG MỘT VÍ DỤ THỰC TẾ

| Bước | Công đoạn | Dữ liệu Đầu vào (Input) | Dữ liệu Đầu ra (Output) | Ý nghĩa thực tế |
| :--- | :--- | :--- | :--- | :--- |
| **2.1** | Ánh xạ Đa thức | Tín hiệu con ngươi thô (x, y) | Pixel màn hình (u=960, v=540) | Mắt bạn đang nhìn vào chính giữa màn hình |
| **2.2** | Chuẩn hóa Pixel | Pixel (960, 540) & Ma trận K | Tọa độ chuẩn hóa (x_norm=0, y_norm=0) | Điểm nhìn nằm đúng trục quang học chính |
| **2.3** | Dựng Tia 3D | Tọa độ chuẩn & Depth Map Z=0.85m | Tọa độ Camera P_c = [0, 0, 0.85]ᵀ | Vật thể nằm trực diện cách camera 85 cm |
| **2.4** | Đổi sang Robot | Tọa độ Camera P_c & Ma trận T (4x4) | Tọa độ Robot P_r = [0.35, 0.50, 0.10]ᵀ | Robot vươn tay sang phải 35cm, tới 50cm, cao 10cm |

---

## 🎯 KẾT LUẬN

Chuỗi 4 công thức toán học này là một đường truyền liên hoàn hoàn chỉnh:
1. **Bước 2.1** giải quyết bài toán **Mắt ➔ Màn hình**.
2. **Bước 2.2** giải quyết bài toán **Màn hình ➔ Góc nhìn chuẩn**.
3. **Bước 2.3** giải quyết bài toán **Góc nhìn 2D ➔ Không gian 3D của Camera**.
4. **Bước 2.4** giải quyết bài toán **Thế giới Camera ➔ Thế giới Cánh tay Robot**.

Nhờ chuỗi công thức này, cái nhìn tự nhiên của con người được chuyển hóa thành hành động cơ khí chính xác thời gian thực của robot chỉ trong **2.97 miligiây**!
