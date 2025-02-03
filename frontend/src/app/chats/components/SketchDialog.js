'use client';

import { useState, useRef } from 'react';
import { ReactSketchCanvas } from 'react-sketch-canvas';
import { Eraser } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

export function SketchDialog({ open, onOpenChange, onSave }) {
  const [strokeColor, setStrokeColor] = useState('#000000');
  const [isEraser, setIsEraser] = useState(false);
  const canvasRef = useRef();

  const handleSketchSave = async () => {
    const paths = await canvasRef.current.exportPaths();
    if (paths.length === 0) {
      onOpenChange(false);
      return;
    }

    const sketch = await canvasRef.current.exportImage('png');
    if (sketch) {
      onSave(sketch);
      onOpenChange(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Sketch</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-4 mb-2">
            <input
              type="color"
              value={strokeColor}
              onChange={(e) => {
                setStrokeColor(e.target.value);
                setIsEraser(false);
              }}
              className="w-8 h-8"
            />
            <Button
              variant={isEraser ? 'secondary' : 'outline'}
              onClick={() => setIsEraser(!isEraser)}
              className="gap-2"
            >
              <Eraser className="h-4 w-4" />
              Eraser
            </Button>
          </div>
          <ReactSketchCanvas
            ref={canvasRef}
            width="100%"
            height="400px"
            strokeWidth={4}
            strokeColor={isEraser ? '#ffffff' : strokeColor}
            eraserWidth={20}
          />
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => canvasRef.current.clearCanvas()}
            >
              Clear
            </Button>
            <Button variant="outline" onClick={() => canvasRef.current.undo()}>
              Undo
            </Button>
            <Button onClick={handleSketchSave}>Save</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
