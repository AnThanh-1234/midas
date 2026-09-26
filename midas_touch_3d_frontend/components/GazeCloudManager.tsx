'use client';
import { useEffect, useState } from 'react';
import { useGazeStore } from '../store/useGazeStore';
import Script from 'next/script';

// Extend window interface
declare global {
  interface Window {
    GazeCloudAPI: any;
  }
}

export const GazeCloudManager = () => {
  const isWebcamMode = useGazeStore((state) => state.isWebcamMode);
  const setCalibrated = useGazeStore((state) => state.setCalibrated);
  const setScreenGaze = useGazeStore((state) => state.setScreenGaze);
  const [scriptLoaded, setScriptLoaded] = useState(false);

  const initGazeCloud = () => {
    if (typeof window !== 'undefined' && window.GazeCloudAPI) {
      window.GazeCloudAPI.OnResult = (GazeData: any) => {
        if (GazeData.state === 0 && useGazeStore.getState().isWebcamMode) {
          const ndcX = (GazeData.docX / window.innerWidth) * 2 - 1;
          const ndcY = -(GazeData.docY / window.innerHeight) * 2 + 1;
          useGazeStore.getState().setScreenGaze(ndcX, ndcY);
        }
      };

      window.GazeCloudAPI.OnCalibrationComplete = () => {
        console.log('GazeCloud: Huấn luyện thành công!');
        setCalibrated(true);
      };

      window.GazeCloudAPI.OnCamDenied = () => {
        alert('Vui lòng cấp quyền camera để sử dụng GazeCloudAPI.');
      };
      
      window.GazeCloudAPI.OnError = (msg: string) => {
        console.error("GazeCloud Error:", msg);
      };
    }
  };

  useEffect(() => {
    return () => {
      if (typeof window !== 'undefined' && window.GazeCloudAPI) {
        window.GazeCloudAPI.StopEyeTracking();
      }
    };
  }, []);

  useEffect(() => {
    if (isWebcamMode) {
      if (scriptLoaded && window.GazeCloudAPI) {
        window.GazeCloudAPI.StartEyeTracking();
      } else if (!scriptLoaded) {
        alert("Thư viện đang được tải... Vui lòng thử lại sau vài giây.");
      }
    } else {
      if (scriptLoaded && window.GazeCloudAPI) {
        window.GazeCloudAPI.StopEyeTracking();
      }
    }
  }, [isWebcamMode, scriptLoaded]);

  return (
    <Script 
      src="https://api.gazerecorder.com/GazeCloudAPI.js" 
      strategy="lazyOnload"
      onLoad={() => {
        console.log("GazeCloudAPI script loaded");
        if (window.GazeCloudAPI) {
          window.GazeCloudAPI.UseClickRecalibration = true;
        }
        setScriptLoaded(true);
        useGazeStore.getState().setGazeCloudLoaded(true);
        initGazeCloud();
      }}
    />
  );
};
