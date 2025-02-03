export const resizeImage = async (file, maxWidth = 1000, maxHeight = 1000) => {
  return new Promise((resolve) => {
    const img = new Image();
    const reader = new FileReader();

    reader.onload = (e) => {
      img.src = e.target.result;
      img.onload = () => {
        const canvas = document.createElement('canvas');
        let { width, height } = calculateDimensions(
          img.width,
          img.height,
          maxWidth,
          maxHeight
        );

        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, width, height);

        const resizedDataUrl = canvas.toDataURL(file.type, 0.7);
        resolve({
          data: resizedDataUrl,
          name: file.name,
          type: file.type,
        });
      };
    };
    reader.readAsDataURL(file);
  });
};

export const captureScreenshot = async (maxWidth = 1000, maxHeight = 1000) => {
  const stream = await navigator.mediaDevices.getDisplayMedia({
    preferCurrentTab: true,
    video: {
      displaySurface: 'browser',
    },
  });

  const video = document.createElement('video');
  video.srcObject = stream;

  await new Promise((resolve) => {
    video.onloadedmetadata = resolve;
  });
  video.play();

  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0);

  // Stop all tracks
  stream.getTracks().forEach((track) => track.stop());

  // Resize the screenshot
  let { width, height } = calculateDimensions(
    canvas.width,
    canvas.height,
    maxWidth,
    maxHeight
  );

  const resizedCanvas = document.createElement('canvas');
  resizedCanvas.width = width;
  resizedCanvas.height = height;
  const resizedCtx = resizedCanvas.getContext('2d');
  resizedCtx.drawImage(canvas, 0, 0, width, height);

  return {
    data: resizedCanvas.toDataURL('image/jpeg', 0.7),
    name: 'screenshot.jpg',
    type: 'image/jpeg',
  };
};

const calculateDimensions = (width, height, maxWidth, maxHeight) => {
  if (width > height) {
    if (width > maxWidth) {
      height *= maxWidth / width;
      width = maxWidth;
    }
  } else {
    if (height > maxHeight) {
      width *= maxHeight / height;
      height = maxHeight;
    }
  }
  return { width, height };
};
