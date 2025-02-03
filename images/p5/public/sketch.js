let ball;

function setup() {
  createCanvas(windowWidth, windowHeight);
  // Create ball in middle of screen
  ball = new Ball(width / 2, height / 2);
}

function windowResized() {
  resizeCanvas(windowWidth, windowHeight);
}

function draw() {
  background(0);
  ball.update();
  ball.draw();
}
