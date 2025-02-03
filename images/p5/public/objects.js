// Any objects types go here

class Ball {
  constructor(x, y, size = 30) {
    this.x = x;
    this.y = y;
    this.size = size;
    this.vx = 3;
    this.vy = 2;
  }

  update() {
    // Update position
    this.x += this.vx;
    this.y += this.vy;

    // Bounce off walls
    if (this.x + this.size / 2 > width || this.x - this.size / 2 < 0)
      this.vx *= -1;
    if (this.y + this.size / 2 > height || this.y - this.size / 2 < 0)
      this.vy *= -1;
  }

  draw() {
    fill(255);
    noStroke();
    circle(this.x, this.y, this.size);
  }
}
