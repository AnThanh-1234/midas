# GMM-HMM eye movement classification

Thư mục này chứa mã nghiên cứu và notebook phục vụ pipeline phân loại chuyển động mắt bằng GMM-HMM của project MIDAS.

## Pipeline

Pipeline phân cấp gồm:

1. **Step 0:** K-means và phương pháp elbow để chọn số segment.
2. **Layer 1:** GMM-HMM phân đoạn chuỗi gaze dựa trên tọa độ `x`, `y` hoặc đặc trưng `x`, `y`, `v`.
3. **Layer 2:** GMM-HMM phân loại vận tốc `v` trong từng segment.
4. **Velocity mapping:** Ánh xạ các state theo vận tốc trung bình thành:
   - `0`: Fixation
   - `1`: Smooth Pursuit
   - `2`: Saccade

Ground truth chỉ được dùng khi đánh giá, không được dùng để huấn luyện mô hình.

## Cấu trúc thư mục

```text
Cac_Httm/
├── main.py                         # Chạy pipeline GMM-HMM chính
├── GMM_HMM_full_layer.py           # Pipeline hai tầng
├── GMM_HMM_full_layer_eval.ipynb   # Đánh giá pipeline trên dữ liệu
├── GMM_HMM_layer1.py               # Step 0 + GMM-HMM tầng 1
├── GMM_HMM_layer1_eva.py           # Đánh giá tầng 1
├── GMM_hmm.py                      # Các hàm/mô hình GMM-HMM
├── baseline_one_gmmhmm_overlap.ipynb # Baseline một GMM-HMM
├── Average_deviation.py            # Tính độ lệch và hỗ trợ chọn k
├── dataplot.py                     # Vẽ dữ liệu và kết quả phân cụm
├── sample_create.py                # Tạo/chuẩn bị sample
├── round1_clusters.txt             # Kết quả nhãn tầng 1 đã xuất
└── collect_clasi_train.txt         # Dữ liệu mẫu [x, y, v]
```

## Định dạng dữ liệu

File dữ liệu thường có ba cột:

```text
x y v
```

Trong đó `x`, `y` là tọa độ gaze đã chuẩn hóa và `v` là vận tốc.

Một số script hỗ trợ thêm cột nhãn thật:

```text
x y v label
```

`GMM_HMM_layer1.py` sẽ in các nhãn thật xuất hiện trong từng segment nếu file có cột thứ tư, đồng thời cảnh báo những segment chỉ chứa hai nhãn thật.

## Cài đặt

Khuyến nghị tạo môi trường ảo tại thư mục project MIDAS:

```powershell
cd ..\midas_touch_3d_backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install numpy pandas scipy scikit-learn hmmlearn matplotlib jupyter
```

Nếu đã cài môi trường Python, có thể cài trực tiếp:

```powershell
python -m pip install numpy pandas scipy scikit-learn hmmlearn matplotlib jupyter
```

## Chạy pipeline chính

Từ thư mục `midas\Cac_Httm`:

```powershell
python main.py
```

Kết quả phụ thuộc vào cấu hình và file dữ liệu được khai báo trong script. Kiểm tra phần `if __name__ == "__main__"` và các đường dẫn đầu vào trước khi chạy.

## Chạy Step 0 và Layer 1

Ví dụ dùng dữ liệu mặc định:

```powershell
python GMM_HMM_layer1.py
```

Chọn số cụm thủ công:

```powershell
python GMM_HMM_layer1.py --k 4
```

Dùng đặc trưng `x`, `y`, `v`:

```powershell
python GMM_HMM_layer1.py --features xyv
```

Một số tùy chọn:

```text
--data      đường dẫn file dữ liệu
--k         số cụm; bỏ trống để chọn bằng elbow
--kmax      số cụm tối đa
--features  xy hoặc xyv
--init      kmeans hoặc random
--n_mix     số mixture/state khi dùng random initialization
--n_iter    số vòng lặp Baum-Welch
```

Sau khi chạy, script:

- In chuỗi cluster theo thời gian.
- In tóm tắt các đoạn liên tiếp.
- In phân bố nhãn thật trong từng đoạn nếu có ground truth.
- Lưu nhãn tầng 1 vào `round1_clusters.txt`.
- Hiển thị biểu đồ phân cụm.

## Chạy notebook

Từ thư mục `Cac_Httm`:

```powershell
jupyter notebook
```

Mở một trong các notebook:

- `GMM_HMM_full_layer_eval.ipynb`
- `baseline_one_gmmhmm_overlap.ipynb`

Sau đó chọn **Restart Kernel → Run All** để chạy lại toàn bộ pipeline.

## Chạy phần đánh giá

Các script/notebook đánh giá có thể in:

- Accuracy.
- Precision.
- Recall.
- F1-score.
- Confusion matrix hoặc kết quả theo từng segment tùy file chạy.

Khi đánh giá, bảo đảm dữ liệu và ground truth có cùng số dòng, đồng thời nhãn thuộc nhóm `0`, `1`, `2`.

## Liên hệ với backend MIDAS

Backend production ở thư mục `midas_touch_3d_backend` sử dụng pipeline GMM-HMM được tổ chức trong `notebook_classifier.py` và gọi thông qua `classifier_service.py`.

Mã trong `Cac_Httm` chủ yếu dùng để nghiên cứu, thử nghiệm, trực quan hóa và đánh giá; không phải entry point của API backend thời gian thực.

## Lưu ý

- Tránh dùng đường dẫn tuyệt đối nếu muốn chạy project trên máy khác.
- Với file có cột thứ tư, nhãn thật phải nằm ở cột cuối theo định dạng mà script hỗ trợ.
- GMM-HMM có thể nhạy với số mẫu, covariance type, số mixture và khởi tạo ban đầu.
- Nếu mô hình không hội tụ, thử giảm `n_mix`, tăng `n_iter`, hoặc dùng `--init kmeans`.
