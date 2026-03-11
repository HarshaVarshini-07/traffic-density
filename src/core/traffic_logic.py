import time

class TrafficController:
    """
    Traffic light controller for static prototype.
    Densest lane always gets green first and longest.
    Always cycles through ALL 4 lanes.
    """
    def __init__(self):
        self.num_lanes = 4
        self.current_green_lane = -1  # Will be set on first update
        self.state = "INIT"  # INIT, GREEN, YELLOW, RED_ALL
        
        self.start_time = time.time()
        self.green_duration = 5
        self.yellow_duration = 2
        self.red_clearance_duration = 1
        
        # Density metrics
        self.densities = [0, 0, 0, 0]
        
        # Priority queue: lanes sorted by density each cycle
        self._cycle_order = []
        self._cycle_index = 0
        self._needs_reorder = True  # Force sort on first update
        
        # Emergency Override State
        self.emergency_lane = None
        self.pre_emergency_state = None
        self.pre_emergency_lane = -1
        
    def update(self, densities, emergency_lane=None):
        """
        Updates the traffic light state based on time and densities.
        Immediately sorts by density on first call and at each cycle start.
        Handles emergency vehicle override.
        """
        self.densities = densities
        current_time = time.time()
        
        # --- Handle Emergency Toggle ---
        if emergency_lane is not None and emergency_lane != self.emergency_lane:
            # Entering emergency mode
            print(f"🚦 TRAFFIC LOGIC: Emergency Override triggered for Lane {emergency_lane + 1}!")
            self.pre_emergency_state = self.state
            self.pre_emergency_lane = self.current_green_lane
            self.emergency_lane = emergency_lane
            self.state = "EMERGENCY"
            self.current_green_lane = emergency_lane
            return self.get_light_states()
            
        elif emergency_lane is None and self.emergency_lane is not None:
            # Exiting emergency mode
            print("🚦 TRAFFIC LOGIC: Emergency Override cleared. Resuming normal operation.")
            self.emergency_lane = None
            # Force an all-red state before giving green back to anyone for safety
            self.state = "RED_ALL"
            self.start_time = current_time
            return self.get_light_states()
            
        # If we are currently IN an emergency, just hold the state
        if self.state == "EMERGENCY":
            return self.get_light_states()
            
        # --- Normal Operation ---
        elapsed = current_time - self.start_time
        
        # First call: immediately start with densest lane
        if self.state == "INIT":
            self._reorder_by_density()
            self._cycle_index = 0
            if len(self._cycle_order) > 0:
                self.current_green_lane = self._cycle_order[0]
            else:
                self.current_green_lane = 0
            self._calculate_green_duration()
            self.state = "GREEN"
            self.start_time = current_time
            return self.get_light_states()
        
        if self.state == "GREEN":
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
                # self._calculate_green_duration() happens inside switch_to_next_lane now, or we do it here:
                self._calculate_green_duration()

        return self.get_light_states()

    def _reorder_by_density(self):
        """Sort lanes by density descending. Only include lanes with vehicles."""
        active_lanes = [i for i in range(self.num_lanes) if self.densities[i] > 0]
        
        if active_lanes:
            # Sort active lanes by density (densest first)
            self._cycle_order = sorted(
                active_lanes,
                key=lambda i: self.densities[i],
                reverse=True
            )
        else:
            # No vehicles anywhere — fallback to round-robin all lanes
            self._cycle_order = list(range(self.num_lanes))

    def _switch_to_next_lane(self):
        """Move to next lane. Re-sort by density at start of each cycle."""
        self._cycle_index += 1
        
        if self._cycle_index >= len(self._cycle_order):
            # New cycle: re-sort by current density
            self._cycle_index = 0
            self._reorder_by_density()
        
        if len(self._cycle_order) > 0:
            self.current_green_lane = self._cycle_order[self._cycle_index]
        else:
            self.current_green_lane = 0
        
    def _calculate_green_duration(self):
        """
        Fixed green duration of 20 seconds when vehicles are present.
        """
        total = sum(self.densities)
        
        if total == 0:
            # No cars anywhere: short equal time (fallback)
            self.green_duration = 4
        else:
            # Fixed duration of 20 seconds when density detected
            self.green_duration = 20

    def get_light_states(self):
        """Returns a list of states for each lane: 'R', 'Y', 'G'"""
        states = ['R'] * 4
        
        if self.state == "GREEN" or self.state == "EMERGENCY":
            if 0 <= self.current_green_lane < 4:
                states[self.current_green_lane] = 'G'
        elif self.state == "YELLOW":
            if 0 <= self.current_green_lane < 4:
                states[self.current_green_lane] = 'Y'
        # INIT and RED_ALL: all remain 'R'
        
        return states
