'use client';

import React, { useRef, useEffect, useState } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { PointerLockControls, Environment, Grid, OrbitControls } from '@react-three/drei';
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
  const { targets, activeHoverTargetId } = useGazeStore();

  return (
    <>
      {targets.map((target) => (
        <mesh 
          key={target.id}
          name={target.id}
          userData={{ isTarget: true }}
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
  
  // Smoothing history
  const historyX = useRef<number[]>([]);
  const historyY = useRef<number[]>([]);

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

  useFrame((state) => {
    const { isWebcamMode, screenGaze } = useGazeStore.getState();
    
    let rayOrigin = new THREE.Vector2(0, 0);

    if (isWebcamMode) {
      // Smoothing filter
      historyX.current.push(screenGaze.x);
      historyY.current.push(screenGaze.y);
      if (historyX.current.length > 12) historyX.current.shift();
      if (historyY.current.length > 12) historyY.current.shift();

      const avgX = historyX.current.reduce((a, b) => a + b, 0) / historyX.current.length;
      const avgY = historyY.current.reduce((a, b) => a + b, 0) / historyY.current.length;
      
      rayOrigin.set(avgX, avgY);
    }

    raycaster.setFromCamera(rayOrigin, camera);
    
    // Find intersection with objects (assuming objects have names or are in a group, but we'll just check distance for simplicity)
    // Actually, let's just map camera rotation to normalized coordinates for training data
    
    // Bắn tia Raycaster để tìm vật thể 3D bị nhìn trúng
    const intersects = raycaster.intersectObjects(scene.children, true);
    
    // Tìm vật thể đầu tiên có userData.isTarget
    const hit = intersects.find((intersect) => intersect.object.userData?.isTarget);
    
    let currentlyHoveredId: string | null = null;
    let targetVector = new THREE.Vector3();

    if (hit) {
      currentlyHoveredId = hit.object.name;
      targetVector = hit.point;
    } else {
      // Nếu không trúng vật thể nào, dùng giao điểm với mặt bàn (y=0) để lấy tọa độ nền
      const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
      raycaster.ray.intersectPlane(plane, targetVector);
    }

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

      if (socketRef.current?.connected) {
        socketRef.current.emit('gaze_data', { x: normX, y: normY, v: velocity, timestamp: now });
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
  const { isWebcamMode, isCalibrated } = useGazeStore();
  
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
      
      {!isWebcamMode && <PointerLockControls />}
      {isWebcamMode && isCalibrated && <OrbitControls makeDefault enablePan={false} maxPolarAngle={Math.PI / 2.1} />}
      
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
