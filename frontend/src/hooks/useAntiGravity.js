import { useEffect, useRef, useState } from 'react';

export const useAntiGravity = (options = {}) => {
  const {
    enabled = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_REACT_APP_ENABLE_ANTIGRAVITY === 'true') || true,
    gravity = parseFloat((typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_ANTIGRAVITY_GRAVITY_VECTOR) || '-9.81'),
    drag = 0.98,
    buoyancy = 0.5,
    bounce = 0.7,
  } = options;

  const [isActive, setIsActive] = useState(enabled);
  const elementRef = useRef(null);
  const velocity = useRef({ x: 0, y: 0 });
  const position = useRef({ x: 0, y: 0 });
  const requestRef = useRef();
  const lastTime = useRef();

  const applyImpulse = (x, y) => {
    velocity.current.x += x;
    velocity.current.y += y;
  };

  const toggleGravity = () => {
    setIsActive(prev => !prev);
  };

  const setBuoyancy = (val) => {
    // Optionally update buoyancy state if we need it dynamic
  };

  useEffect(() => {
    if (!isActive || !elementRef.current) {
      if (requestRef.current) cancelAnimationFrame(requestRef.current);
      return;
    }

    const animate = (time) => {
      if (lastTime.current != null) {
        const deltaTime = (time - lastTime.current) / 1000;
        
        // Apply physics
        // g is -9.81, meaning upward acceleration in standard y-down coordinates
        velocity.current.y += (gravity * buoyancy) * deltaTime;
        
        // Air resistance damping
        velocity.current.y *= drag;
        velocity.current.x *= drag;

        position.current.y += velocity.current.y;
        position.current.x += velocity.current.x;

        // Boundary bouncing (upper frame)
        if (position.current.y < -window.innerHeight / 2) {
            position.current.y = -window.innerHeight / 2;
            velocity.current.y *= -bounce;
        }

        elementRef.current.style.transform = `translate(${position.current.x}px, ${position.current.y}px)`;
      }
      lastTime.current = time;
      requestRef.current = requestAnimationFrame(animate);
    };

    requestRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(requestRef.current);
  }, [isActive, gravity, drag, buoyancy, bounce]);

  return { elementRef, toggleGravity, applyImpulse, setBuoyancy, isActive };
};
