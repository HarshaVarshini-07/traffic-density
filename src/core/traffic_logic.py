import time

class TrafficController:
    def __init__(self):
        self.num_lanes = 4
        self.current_green_lane = 0 # 0 to 3
        self.state = "GREEN" # GREEN, YELLOW, RED_ALL
        
        self.start_time = time.time()
        self.green_duration = 5 # Default, will be dynamic
        self.yellow_duration = 2
        self.red_clearance_duration = 1
        
        # density metrics
        self.densities = [0, 0, 0, 0]
        
    def update(self, densities):
        """
        Updates the traffic light state based on time and densities.
        densities: List of vehicle counts per lane [N, E, S, W]
        """
        self.densities = densities
        current_time = time.time()
        elapsed = current_time - self.start_time
        
        if self.state == "GREEN":
            # Check if density is high in other lanes to switch early? 
            # Or just stick to calculated duration.
            # Simple logic: Fixed duration based on density at start of green.
            pass
            
            if elapsed > self.green_duration:
                self.state = "YELLOW"
                self.start_time = current_time
                
        elif self.state == "YELLOW":
            if elapsed > self.yellow_duration:
                self.state = "RED_ALL"
                self.start_time = current_time
                
        elif self.state == "RED_ALL":
            if elapsed > self.red_clearance_duration:
                self._switch_to_next_lane()
                self.state = "GREEN"
                self.start_time = current_time
                self._calculate_green_duration()

        return self.get_light_states()

    def _switch_to_next_lane(self):
        # Round robin for now, but can be smart (skip empty lanes)
        self.current_green_lane = (self.current_green_lane + 1) % self.num_lanes
        
        # Simple skip logic: if next lane empty, try next
        # (Prevent infinite loop if all empty)
        original_next = self.current_green_lane
        for _ in range(3):
            if self.densities[self.current_green_lane] == 0:
                 self.current_green_lane = (self.current_green_lane + 1) % self.num_lanes
            else:
                break
        
    def _calculate_green_duration(self):
        # Dynamic duration based on vehicle count
        # E.g., 2 seconds per vehicle, min 5s, max 30s
        count = self.densities[self.current_green_lane]
        self.green_duration = max(5, min(30, count * 2))

    def get_light_states(self):
        """
        Returns a list of states for each lane: 'R', 'Y', 'G'
        """
        states = ['R'] * 4
        
        if self.state == "GREEN":
            states[self.current_green_lane] = 'G'
        elif self.state == "YELLOW":
            states[self.current_green_lane] = 'Y'
        # else RED_ALL, all remain 'R'
        
        return states
