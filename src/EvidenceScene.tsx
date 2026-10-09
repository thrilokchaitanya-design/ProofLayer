import { Canvas, useFrame } from '@react-three/fiber';
import { Edges, Line } from '@react-three/drei';
import { useReducedMotion } from 'framer-motion';
import { Component, useRef, type ReactNode } from 'react';
import * as THREE from 'three';

type EvidencePhase = 'processing' | 'conflict' | 'insufficient' | 'review' | 'evidence' | 'selected' | 'library' | 'idle';

function Sheet({ position, rotation = 0, tone }: { position: [number, number, number]; rotation?: number; tone: string }) {
  return <mesh position={position} rotation={[0, 0, rotation]} castShadow receiveShadow>
    <boxGeometry args={[2.55, 0.055, 3.18]} />
    <meshStandardMaterial color={tone} roughness={0.78} metalness={0.015} />
    <Edges scale={1.002} threshold={18} color="#a7adb1" />
  </mesh>;
}

function DocumentSculpture({ phase, evidenceCount }: { phase: EvidencePhase; evidenceCount: number }) {
  const root = useRef<THREE.Group>(null);
  const nodes = useRef<THREE.Group>(null);
  const reduced = useReducedMotion();
  const visibleNodes = Math.min(evidenceCount, 3);
  const conflict = phase === 'conflict';
  const insufficient = phase === 'insufficient';
  const processing = phase === 'processing';

  useFrame(({ pointer }) => {
    if (!root.current) return;
    const blend = reduced ? 1 : 0.075;
    root.current.rotation.y = THREE.MathUtils.lerp(root.current.rotation.y, reduced ? 0 : pointer.x * 0.16, blend);
    root.current.rotation.x = THREE.MathUtils.lerp(root.current.rotation.x, reduced ? 0 : -pointer.y * 0.09, blend);
    root.current.position.y = THREE.MathUtils.lerp(root.current.position.y, processing ? 0.1 : 0, blend);
    if (nodes.current) {
      const targetX = conflict ? 1.04 : insufficient ? 1.14 : 0.48;
      nodes.current.position.x = THREE.MathUtils.lerp(nodes.current.position.x, targetX, blend);
    }
  });

  return <group ref={root}>
    <Sheet position={[0, -0.13, 0.02]} rotation={-0.035} tone="#dddcd5" />
    <Sheet position={[-0.09, -0.045, -0.015]} rotation={0.022} tone="#eeede7" />
    <Sheet position={[0.055, 0.045, 0.045]} rotation={-0.012} tone="#fbfaf5" />
    <mesh position={[0.055, 0.078, 0.08]}>
      <boxGeometry args={[1.74, 0.009, 0.018]} />
      <meshStandardMaterial color="#aeb2af" />
    </mesh>
    {[-0.28, -0.14, 0, 0.14, 0.28].map((z, index) => <mesh key={z} position={[-0.15, 0.082, z - 0.35]}>
      <boxGeometry args={[index === 1 ? 1.42 : 1.82, 0.008, 0.012]} />
      <meshStandardMaterial color="#c5c6c0" />
    </mesh>)}
    <mesh position={[-0.73, 0.12, 0.08]}>
      <boxGeometry args={[0.12, 0.026, 0.12]} />
      <meshStandardMaterial color="#c14b3c" roughness={0.44} />
      <Edges scale={1.02} color="#8f332c" />
    </mesh>
    {visibleNodes > 0 && <group ref={nodes}>
      <Line points={[[0.43, 0.13, -0.22], [0.48, 0.13, -0.22 - (visibleNodes - 1) * 0.28]]} color={conflict || insufficient ? '#dc6859' : '#5a77dc'} lineWidth={1.25} />
      {Array.from({ length: visibleNodes }, (_, index) => {
        const isSeparated = (conflict && index === visibleNodes - 1) || (insufficient && index === 0);
        const z = -0.22 - index * 0.28;
        return <mesh key={index} position={[0.48, 0.17 + (isSeparated ? 0.09 : 0), z]} castShadow>
          <sphereGeometry args={[0.065, 20, 20]} />
          <meshStandardMaterial color={isSeparated ? '#d76b57' : '#5370d5'} metalness={0.18} roughness={0.28} />
        </mesh>;
      })}
    </group>}
    {insufficient && <mesh position={[1.12, 0.19, -0.73]}>
      <octahedronGeometry args={[0.065, 0]} />
      <meshStandardMaterial color="#c14b3c" roughness={0.35} />
    </mesh>}
  </group>;
}

function StaticFallback() {
  return <div className="webgl-fallback" role="img" aria-label="Static document illustration">
    <div className="fallback-sheet fallback-sheet-back" />
    <div className="fallback-sheet fallback-sheet-front"><i /><i /><i /><i /><b /></div>
    <span>3D VIEW UNAVAILABLE · SOURCE WORKSPACE REMAINS ACTIVE</span>
  </div>;
}

class SceneErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? <StaticFallback /> : this.props.children; }
}

export default function EvidenceScene({ phase = 'idle', evidenceCount = 0 }: { phase?: EvidencePhase; evidenceCount?: number }) {
  const reduced = useReducedMotion();
  return <div className="canvas-host">
    <SceneErrorBoundary>
      <Canvas shadows fallback={null} frameloop={reduced ? 'demand' : 'always'} camera={{ position: [3.2, 3.65, 5.15], fov: 35 }} dpr={[1, 1.5]} gl={{ alpha: true, antialias: true }}>
        <ambientLight intensity={1.4} />
        <directionalLight position={[3.7, 5.2, 3.8]} intensity={2.35} castShadow shadow-mapSize={[1024, 1024]} />
        <DocumentSculpture phase={phase} evidenceCount={evidenceCount} />
      </Canvas>
    </SceneErrorBoundary>
    {evidenceCount > 0 && <div className="scene-count" aria-live="polite"><span>{evidenceCount.toString().padStart(2, '0')}</span> RETRIEVED PASSAGES</div>}
    <div className="scene-annotation annotation-top"><span>01</span> CLAIM / REVIEW</div>
    <div className="scene-annotation annotation-bottom"><span>02</span> SOURCE / PAGE</div>
    <div className="scene-crosshair" aria-hidden="true">+</div>
  </div>;
}
