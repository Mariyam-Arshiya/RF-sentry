class KalmanFilter:
    def __init__(self, process_var=1e-3, measure_var=0.1):
        self.Q = process_var
        self.R = measure_var
        self.P = 1.0
        self.x = None

    def update(self, z):
        if self.x is None:
            self.x = z
            return z
        self.P = self.P + self.Q
        K      = self.P / (self.P + self.R)
        self.x = self.x + K * (z - self.x)
        self.P = (1 - K) * self.P
        return self.x
