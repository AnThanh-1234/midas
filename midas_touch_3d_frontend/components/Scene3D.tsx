'use client';

import React, { useRef, useEffect, useState } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { PointerLockControls, Environment, Grid, useCursor } from '@react-three/drei';
import * as THREE from 'three';
import { io, Socket } from 'socket.io-client';
import { useGazeStore } from '../store/useGazeStore';

const SOCKET_URL = process.env.NEXT_PUBLIC_SOCKET_URL || 'http://127.0.0.1:8001';

// Robot Arm Component
const RobotArm = () => {
  const robotPosition = useGazeStore((state) => state.robotPosition);
  const ref = useRef<THREE.Mesh>(null);

  useFrame((state, delta) => {
    if (ref.current) {
      // Interpolate position smoothly
      ref.current.position.lerp(new THREE.Vector3(...robotPosition), delta * 5);
    }
  });

  return (
    <mesh ref={ref} position={robotPosition} castShadow>
      <cylinderGeometry args={[0.2, 0.2, 2, 32]} />
      <meshStandardMaterial color="#94a3b8" metalness={0.8} roughness={0.2} />
    </mesh>
  );
};

// Target Objects
const TargetObjects = () => {
  const { targets, setHoverTarget, updateTargetGraspProgress, label, activeHoverTargetId } = useGazeStore();
  const fixationTimerRef = useRef<{ [key: string]: number }>({});
  
  // Track hovered target id from raycaster in GazeController
  // The actual collision logic is handled there and updates Zustand.
  // Here we just render them.

  return (
    <>
      {targets.map((target) => (
        <mesh 
          key={target.id} 
          position={target.position}
          castShadow
          receiveShadow
        >
          {target.geometry === 'box' && <boxGeometry args={[0.8, 0.8, 0.8]} />}
          {target.geometry === 'sphere' && <sphereGeometry args={[0.5, 32, 32]} />}
          {target.geometry === 'cylinder' && <cylinderGeometry args={[0.4, 0.4, 1, 32]} />}
          
          <meshStandardMaterial 
            color={target.isGrasped ? '#10b981' : target.color} 
            emissive={activeHoverTargetId === target.id && !target.isGrasped ? target.color : '#000000'}
            emissiveIntensity={activeHoverTargetId === target.id && !target.isGrasped ? 0.5 : 0}
            metalness={0.3} 
            roughness={0.4} 
          />
        </mesh>
      ))}
    </>
  );
};

// Gaze Controller - handles raycasting, math, and WebSocket
const GazeController = () => {
  const { camera, scene, pointer } = useThree();
  const socketRef = useRef<Socket | null>(null);
  const { setGazeData, setConnected, targets, setHoverTarget, updateTargetGraspProgress, label } = useGazeStore();
  
  const raycaster = new THREE.Raycaster();
  const lastPosRef = useRef<{ x: number; y: number; time: number } | null>(null);
  const fixationTimerRef = useRef<{ [key: string]: number }>({});

  useEffect(() => {
    const socket = io(SOCKET_URL, {
      transports: ['websocket', 'polling'],
      reconnectionAttempts: 10,
    });
    socketRef.current = socket;

    socket.on('connect', () => setConnected(true));
    socket.on('disconnect', () => setConnected(false));
    socket.on('gaze_result', (data) => {
      setGazeData(data.x, data.y, data.v, data.label, data.label_name);
    });

    return () => {
      socket.disconnect();
    };
  }, []);

  const isWebGazerInitialized = useRef(false);
  const isWebcamMode = useGazeStore((state) => state.isWebcamMode);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    
    const setupWebgazer = () => {
      console.log("[WebGazer] setupWebgazer called. isWebcamMode:", isWebcamMode);
      
      if (isWebcamMode) {
        if (window.webgazer && !isWebGazerInitialized.current) {
          console.log("[WebGazer] Initializing for the first time...");
          window.webgazer.setGazeListener((data: any, elapsedTime: number) => {
            if (data == null || !useGazeStore.getState().isWebcamMode) return;
            
            const ndcX = (data.x / window.innerWidth) * 2 - 1;
            const ndcY = -(data.y / window.innerHeight) * 2 + 1;
            
            useGazeStore.getState().setScreenGaze(ndcX, ndcY);
          }).begin();

          window.webgazer.showVideoPreview(true).showPredictionPoints(true);
          isWebGazerInitialized.current = true;
          console.log("[WebGazer] Started successfully.");
        } else if (window.webgazer && isWebGazerInitialized.current) {
          console.log("[WebGazer] Resuming...");
          window.webgazer.resume();
          window.webgazer.showVideoPreview(true).showPredictionPoints(true);
        }
      } else {
        if (window.webgazer && window.webgazer.isReady && window.webgazer.isReady()) {
            console.log("[WebGazer] Pausing...");
            window.webgazer.pause();
            window.webgazer.showVideoPreview(false).showPredictionPoints(false);
        }
      }
    };

    let checkWebgazer: NodeJS.Timeout;
    if (window.webgazer) {
      setupWebgazer();
    } else {
      checkWebgazer = setInterval(() => {
        if (window.webgazer) {
          console.log("[WebGazer] Script loaded successfully from CDN.");
          clearInterval(checkWebgazer);
          setupWebgazer();
        }
      }, 100);
    }

    return () => {
       if (checkWebgazer) clearInterval(checkWebgazer);
    };
  }, [isWebcamMode]); // Re-run when isWebcamMode changes

  // Global cleanup when component unmounts entirely
  useEffect(() => {
    return () => {
       if (typeof window !== 'undefined' && window.webgazer && window.webgazer.isReady && window.webgazer.isReady()) {
         window.webgazer.pause();
         window.webgazer.showVideoPreview(false).showPredictionPoints(false);
       }
    };
  }, []);

  useFrame((state) => {
    const { isWebcamMode, screenGaze } = useGazeStore.getState();
    
    if (isWebcamMode) {
      // Raycast from webcam eye gaze position on screen
      raycaster.setFromCamera(new THREE.Vector2(screenGaze.x, screenGaze.y), camera);
    } else {
      // Raycast from center of camera (pointer is [0,0] for PointerLock)
      raycaster.setFromCamera(new THREE.Vector2(0, 0), camera);
    }
    
    // Find intersection with objects (assuming objects have names or are in a group, but we'll just check distance for simplicity)
    // Actually, let's just map camera rotation to normalized coordinates for training data
    
    // Instead of full 3D to 2D mapping which can be complex, we can use the intersection point on the table (y=0 plane)
    const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
    const targetVector = new THREE.Vector3();
    raycaster.ray.intersectPlane(plane, targetVector);

    if (targetVector) {
      // Map x from [-5, 5] to [0, 1] and z from [-5, 5] to [0, 1]
      const normX = Math.max(0, Math.min(1, (targetVector.x + 5) / 10));
      const normY = Math.max(0, Math.min(1, (targetVector.z + 5) / 10));
      
      const now = performance.now();
      let velocity = 0;

      if (lastPosRef.current) {
        const dx = normX - lastPosRef.current.x;
        const dy = normY - lastPosRef.current.y;
        const dt = (now - lastPosRef.current.time) / 1000;

        if (dt > 0) {
          velocity = Math.sqrt(dx * dx + dy * dy) / dt;
        }
      }

      lastPosRef.current = { x: normX, y: normY, time: now };

      // Send to server at ~30fps by throttling if needed, but useFrame is 60fps. 
      // We'll send every frame for smoothness in this demo.
      if (socketRef.current?.connected) {
        socketRef.current.emit('gaze_data', { x: normX, y: normY, v: velocity, timestamp: now });
      }

      // Check collision with targets
      let currentlyHoveredId: string | null = null;
      for (const t of targets) {
        const dx = targetVector.x - t.position[0];
        const dz = targetVector.z - t.position[2];
        const dist = Math.sqrt(dx*dx + dz*dz);
        if (dist < 1.0) { // hover radius
          currentlyHoveredId = t.id;
          break;
        }
      }
      
      const prevHoveredId = useGazeStore.getState().activeHoverTargetId;
      if (currentlyHoveredId !== prevHoveredId) {
        setHoverTarget(currentlyHoveredId);
      }

      // Midas touch logic
      const currentLabel = useGazeStore.getState().label;
      targets.forEach((target) => {
        if (target.id === currentlyHoveredId && currentLabel === 0) {
          const startTime = fixationTimerRef.current[target.id] || Date.now();
          if (!fixationTimerRef.current[target.id]) fixationTimerRef.current[target.id] = startTime;
          
          const elapsed = Date.now() - startTime;
          const progress = Math.min(100, (elapsed / 800) * 100); // 800ms for 3D demo

          if (progress >= 100 && !target.isGrasped) {
            updateTargetGraspProgress(target.id, 100, true);
          } else if (!target.isGrasped && Math.abs(target.graspProgress - progress) > 3) {
            updateTargetGraspProgress(target.id, progress, false);
          }
        } else {
          delete fixationTimerRef.current[target.id];
          if (!target.isGrasped && target.graspProgress !== 0) {
            updateTargetGraspProgress(target.id, 0, false);
          }
        }
      });
    }
  });

  return null;
};

export const Scene3D = () => {
  return (
    <Canvas shadows camera={{ position: [0, 4, 6], fov: 60 }}>
      <color attach="background" args={['#0f172a']} />
      <ambientLight intensity={0.5} />
      <directionalLight 
        position={[10, 10, 5]} 
        intensity={1} 
        castShadow 
        shadow-mapSize-width={1024} 
        shadow-mapSize-height={1024} 
      />
      
      <PointerLockControls />
      
      <GazeController />
      
      {/* Table Floor */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.1, 0]} receiveShadow>
        <planeGeometry args={[20, 20]} />
        <meshStandardMaterial color="#1e293b" />
      </mesh>
      
      <Grid position={[0, 0.01, 0]} args={[20, 20]} cellColor="#334155" sectionColor="#475569" fadeDistance={15} />

      <TargetObjects />
      <RobotArm />
      
      <Environment preset="city" />
    </Canvas>
  );
};
