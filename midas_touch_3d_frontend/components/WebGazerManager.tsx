'use client';
import { useEffect, useRef, useState } from 'react';
import { useGazeStore } from '../store/useGazeStore';

// 13 điểm trên màn hình để tăng độ chính xác của AI
const CALIBRATION_POINTS = [
  { x: 0.1, y: 0.1 }, { x: 0.5, y: 0.1 }, { x: 0.9, y: 0.1 },
  { x: 0.25, y: 0.25 }, { x: 0.75, y: 0.25 },
  { x: 0.1, y: 0.5 }, { x: 0.5, y: 0.5 }, { x: 0.9, y: 0.5 },
  { x: 0.25, y: 0.75 }, { x: 0.75, y: 0.75 },
  { x: 0.1, y: 0.9 }, { x: 0.5, y: 0.9 }, { x: 0.9, y: 0.9 },
];

export const WebGazerManager = () => {
  const isInitialized = useRef(false);
  const [isReady, setIsReady] = useState(false);
  const [currentPointIndex, setCurrentPointIndex] = useState(-1);
  
  const isWebcamMode = useGazeStore((state) => state.isWebcamMode);
  const isCalibrated = useGazeStore((state) => state.isCalibrated);
  const setCalibrated = useGazeStore((state) => state.setCalibrated);

  const handleStartCamera = async () => {
    if (typeof window === 'undefined' || !window.webgazer) {
      alert("Lỗi: Thư viện WebGazer chưa tải xong! Đợi một chút hoặc kiểm tra mạng.");
      return;
    }

    try {
      if (window.webgazer.clearData) {
         window.webgazer.clearData();
      }

      await window.webgazer
        .setGazeListener((data: any, elapsedTime: number) => {
          if (data == null || !useGazeStore.getState().isWebcamMode) return;
          const ndcX = (data.x / window.innerWidth) * 2 - 1;
          const ndcY = -(data.y / window.innerHeight) * 2 + 1;
          useGazeStore.getState().setScreenGaze(ndcX, ndcY);
        })
        .begin(); 

      // Gọi sau khi begin() để đảm bảo event listeners đã được tạo trước khi xóa
      window.webgazer.removeMouseEventListeners();

      window.webgazer.showVideoPreview(true);
      window.webgazer.showPredictionPoints(true);

      isInitialized.current = true;
      setIsReady(true);
    } catch (error) {
      console.error("WebGazer Error:", error);
      alert("Không thể khởi tạo WebGazer. Vui lòng cho phép quyền Camera trên trình duyệt!");
    }
  };

  // Logic tự động bơm dữ liệu cho WebGazer (Auto-Calibration)
  useEffect(() => {
    if (currentPointIndex >= 0 && currentPointIndex < CALIBRATION_POINTS.length && isReady) {
      const point = CALIBRATION_POINTS[currentPointIndex];
      const pxX = window.innerWidth * point.x;
      const pxY = window.innerHeight * point.y;
      
      let recordInterval: NodeJS.Timeout;
      
      // Đợi 1.5 giây để mắt người dùng kịp tìm và nhìn cố định vào chấm đỏ mới, sau đó mới bắt đầu ghi nhận
      const delayBeforeRecord = setTimeout(() => {
        recordInterval = setInterval(() => {
          if (window.webgazer && window.webgazer.recordScreenPosition) {
            window.webgazer.recordScreenPosition(pxX, pxY, 'click');
          }
        }, 100);
      }, 1500);

      // Đứng yên ở điểm này tổng cộng 3.5 giây, sau đó chuyển sang điểm tiếp theo
      const moveTimeout = setTimeout(() => {
        clearInterval(recordInterval);
        setCurrentPointIndex((prev) => prev + 1);
      }, 3500);

      return () => {
        clearTimeout(delayBeforeRecord);
        clearInterval(recordInterval);
        clearTimeout(moveTimeout);
      };
    } else if (currentPointIndex >= CALIBRATION_POINTS.length) {
      // Hoàn thành 13 điểm
      setCalibrated(true);
      // Có thể tắt VideoPreview đi để giao diện 3D đẹp hơn
      if (window.webgazer) {
        window.webgazer.showVideoPreview(false);
        window.webgazer.showPredictionPoints(false); // Tắt chấm đỏ mặc định của WebGazer
      }
    }
  }, [currentPointIndex, isReady, setCalibrated]);

  // Quản lý trạng thái Pause/Resume khi chuyển chế độ
  useEffect(() => {
    if (isWebcamMode) {
      if (isInitialized.current && window.webgazer) {
        window.webgazer.resume();
        window.webgazer.showVideoPreview(true);
        window.webgazer.showPredictionPoints(true);
      }
    } else {
      if (isInitialized.current && window.webgazer) {
        window.webgazer.pause();
        window.webgazer.showVideoPreview(false);
        window.webgazer.showPredictionPoints(false);
      }
    }
  }, [isWebcamMode]);
  
  // Cleanup
  useEffect(() => {
    return () => {
      if (isInitialized.current && window.webgazer) {
        window.webgazer.pause();
        window.webgazer.showVideoPreview(false);
        window.webgazer.showPredictionPoints(false);
      }
    };
  }, []);

  if (isWebcamMode && !isCalibrated) {
    // Nếu đang trong quá trình chạy chấm đỏ
    if (currentPointIndex >= 0 && currentPointIndex < CALIBRATION_POINTS.length) {
      const point = CALIBRATION_POINTS[currentPointIndex];
      return (
        <div className="absolute inset-0 z-[100] bg-slate-900 overflow-hidden pointer-events-none">
          <p className="absolute top-8 w-full text-center text-xl text-white font-bold">
            Hãy nhìn chằm chằm vào TÂM BIA MÀU XANH LÁ... ({currentPointIndex + 1}/{CALIBRATION_POINTS.length})
          </p>
          {/* Bia ngắm màu xanh lá (Target) */}
          <div 
            className="absolute flex items-center justify-center transition-all duration-500 ease-in-out -translate-x-1/2 -translate-y-1/2"
            style={{
              left: `${point.x * 100}%`,
              top: `${point.y * 100}%`
            }}
          >
            <div className="absolute w-12 h-12 bg-emerald-500/20 rounded-full animate-ping" />
            <div className="absolute w-8 h-8 border-2 border-emerald-400 rounded-full" />
            <div className="absolute w-3 h-3 bg-emerald-500 rounded-full shadow-[0_0_15px_#10b981]" />
          </div>
        </div>
      );
    }

    // Màn hình bắt đầu
    return (
      <div className="absolute inset-0 z-[100] bg-slate-900 flex flex-col items-center justify-center text-center">
        <h2 className="text-3xl font-bold text-white mb-6 relative z-10">Hiệu Chuẩn Ánh Nhìn Tự Động</h2>
        <p className="text-slate-300 mb-8 max-w-xl text-lg leading-relaxed relative z-10">
          Chỉ cần <b>nhìn chằm chằm vào bia ngắm MÀU XANH LÁ</b> trên màn hình. Không cần dùng chuột! Hệ thống sẽ tự động hiệu chuẩn mắt cho bạn.
        </p>
        
        {!isReady ? (
          <button 
            onClick={(e) => { e.stopPropagation(); handleStartCamera(); }}
            className="relative z-20 px-8 py-4 bg-blue-600 hover:bg-blue-500 text-white rounded-xl shadow-lg font-bold text-lg transition-colors mb-4"
          >
            Bật Camera & Xin Quyền
          </button>
        ) : (
          <button 
            onClick={() => setCurrentPointIndex(0)}
            className="relative z-20 px-8 py-4 bg-emerald-500 hover:bg-emerald-600 text-white rounded-xl shadow-lg font-bold text-lg transition-colors mt-4"
          >
            Bắt đầu Auto-Calibration
          </button>
        )}
      </div>
    );
  }

  return null;
};
