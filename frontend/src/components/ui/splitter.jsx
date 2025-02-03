import React, { useState, useRef, useEffect } from 'react';

const Splitter = ({
  children,
  className = '',
  minLeftWidth = 300,
  minRightWidth = 50,
  defaultLeftWidth = '70%',
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [leftWidth, setLeftWidth] = useState(defaultLeftWidth);
  const containerRef = useRef(null);
  const leftPaneRef = useRef(null);
  const rightPaneRef = useRef(null);

  const handleMouseDown = (e) => {
    e.preventDefault();
    setIsDragging(true);
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'col-resize';
  };

  const handleTouchStart = (e) => {
    e.preventDefault();
    setIsDragging(true);
    document.body.style.userSelect = 'none';
  };

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isDragging || !containerRef.current) return;

      const container = containerRef.current;
      const containerRect = container.getBoundingClientRect();
      const newLeftWidth = Math.max(
        minLeftWidth,
        Math.min(
          e.clientX - containerRect.left,
          containerRect.width - minRightWidth
        )
      );

      setLeftWidth(newLeftWidth);
    };

    const handleTouchMove = (e) => {
      if (!isDragging || !containerRef.current) return;

      const touch = e.touches[0];
      const container = containerRef.current;
      const containerRect = container.getBoundingClientRect();
      const newLeftWidth = Math.max(
        minLeftWidth,
        Math.min(
          touch.clientX - containerRect.left,
          containerRect.width - minRightWidth
        )
      );

      setLeftWidth(newLeftWidth);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
    };

    const handleTouchEnd = () => {
      setIsDragging(false);
      document.body.style.userSelect = '';
    };

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.addEventListener('touchmove', handleTouchMove);
      document.addEventListener('touchend', handleTouchEnd);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.removeEventListener('touchmove', handleTouchMove);
      document.removeEventListener('touchend', handleTouchEnd);
    };
  }, [isDragging, minLeftWidth, minRightWidth]);

  const [leftChild, rightChild] = React.Children.toArray(children);

  return (
    <div
      ref={containerRef}
      className={`flex h-full w-full select-none ${className}`}
      style={{ cursor: isDragging ? 'col-resize' : 'default' }}
    >
      <div
        ref={leftPaneRef}
        className="flex-shrink-0"
        style={{
          width: typeof leftWidth === 'number' ? `${leftWidth}px` : leftWidth,
        }}
      >
        {leftChild}
      </div>

      <div
        className={`w-1 bg-border hover:bg-primary/10 cursor-col-resize flex-shrink-0 relative ${
          isDragging ? 'bg-primary/10' : ''
        }`}
        onMouseDown={handleMouseDown}
        onTouchStart={handleTouchStart}
      >
        <div className="absolute inset-y-0 -left-2 right-2 cursor-col-resize" />
      </div>

      <div ref={rightPaneRef} className="flex-1 min-w-0">
        {rightChild}
      </div>
    </div>
  );
};

export default Splitter;
