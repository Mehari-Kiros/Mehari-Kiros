import math
import random

# AODV Message Types
RREQ = 1
RREP = 2
RERR = 3
DATA = 4

class DataMessage:
    def __init__(self, dest_id, packet_id):
        self.type = DATA
        self.dest_id = dest_id
        self.packet_id = packet_id

class RREQMessage:
    def __init__(self, rreq_id, originator_id, originator_seq, dest_id, dest_seq, hop_count):
        self.type = RREQ
        self.rreq_id = rreq_id
        self.originator_id = originator_id
        self.originator_seq = originator_seq
        self.dest_id = dest_id
        self.dest_seq = dest_seq
        self.hop_count = hop_count

class RREPMessage:
    def __init__(self, originator_id, dest_id, dest_seq, hop_count, lifetime, trust_value):
        self.type = RREP
        self.originator_id = originator_id
        self.dest_id = dest_id
        self.dest_seq = dest_seq
        self.hop_count = hop_count
        self.lifetime = lifetime
        self.trust_value = trust_value

class RoutingTableEntry:
    def __init__(self, destination, next_hop, hop_count, seq_num, lifetime, trust_value):
        self.destination = destination
        self.next_hop = next_hop
        self.hop_count = hop_count
        self.seq_num = seq_num
        self.lifetime = lifetime
        self.trust_value = trust_value

class Node:
    def __init__(self, node_id, x, y, transmission_range=200):
        self.node_id = node_id
        self.x = x
        self.y = y
        self.transmission_range = transmission_range
        self.neighbors = []
        self.routing_table = {}
        self.seq_num = 0
        self.rreq_id = 0
        self.rreq_cache = set() # To store (originator_id, rreq_id) tuples
        self.trust_history = {} # {neighbor_id: [trust_events]}
        self.gl_calculus = GL_Calculus()
        self.use_gl_calculus = True # Switch to disable for standard AODV
        print(f"Node {self.node_id} created at ({self.x}, {self.y})")

    def find_neighbors(self, all_nodes):
        """
        Discovers neighboring nodes within the transmission range.
        """
        for node in all_nodes:
            if node != self:
                distance = math.sqrt((self.x - node.x)**2 + (self.y - node.y)**2)
                if distance <= self.transmission_range:
                    self.neighbors.append(node)
        # print(f"Node {self.node_id} has neighbors: {[n.node_id for n in self.neighbors]}")

    def __repr__(self):
        return f"Node({self.node_id})"

    def initiate_route_discovery(self, dest_id, simulation):
        """
        Starts a route discovery process for a destination.
        """
        print(f"Node {self.node_id} initiating route discovery for Node {dest_id}")
        self.rreq_id += 1
        self.seq_num += 1

        rreq = RREQMessage(
            rreq_id=self.rreq_id,
            originator_id=self.node_id,
            originator_seq=self.seq_num,
            dest_id=dest_id,
            dest_seq=0, # Unknown, will be updated by destination
            hop_count=0
        )
        self.rreq_cache.add((rreq.originator_id, rreq.rreq_id))
        simulation.broadcast(self, rreq)

    def receive_message(self, message, sender, simulation):
        """
        Handles incoming messages.
        """
        if message.type == RREQ:
            self.process_rreq(message, sender, simulation)
        elif message.type == RREP:
            self.process_rrep(message, sender, simulation)
        elif message.type == DATA:
            self.process_data(message, sender, simulation)
        # Add handlers for RERR later

    def send_data(self, dest_id, num_packets, simulation):
        """
        Sends a stream of data packets to a destination.
        """
        print(f"Node {self.node_id} sending {num_packets} data packets to {dest_id}")
        for i in range(num_packets):
            data_packet = DataMessage(dest_id, i)
            next_hop_id = self.routing_table[dest_id].next_hop
            next_hop_node = simulation.get_node(next_hop_id)
            simulation.unicast(self, next_hop_node, data_packet)
            simulation.packets_sent += 1

    def process_data(self, message, sender, simulation):
        """
        Processes a received data packet.
        """
        if self.node_id == message.dest_id:
            simulation.packets_delivered += 1
            # print(f"Node {self.node_id} received data packet {message.packet_id}")
            return

        # Forward the packet
        if message.dest_id in self.routing_table:
            # Simulate link failure based on trust
            trust_history = self.trust_history.get(sender.node_id, [1.0])
            trust_value = self.gl_calculus.calculate_derivative(trust_history)
            if random.random() > trust_value:
                # print(f"Node {self.node_id} dropped packet from {sender.node_id} (trust: {trust_value:.2f})")
                return # Packet dropped

            next_hop_id = self.routing_table[message.dest_id].next_hop
            next_hop_node = simulation.get_node(next_hop_id)
            simulation.unicast(self, next_hop_node, message)

    def process_rreq(self, message, sender, simulation):
        """
        Processes a received RREQ message.
        """
        print(f"Node {self.node_id} received RREQ from {sender.node_id} for {message.dest_id}")

        # Discard if we've seen this RREQ before
        if (message.originator_id, message.rreq_id) in self.rreq_cache:
            return

        self.rreq_cache.add((message.originator_id, message.rreq_id))

        # Update route to the originator
        # (Simplified for now)

        # Update or create a route to the originator
        self.update_routing_table(message.originator_id, sender.node_id, message.hop_count, message.originator_seq, 1.0) # Assume trust 1 for reverse path

        # If this node is the destination, send RREP
        if self.node_id == message.dest_id:
            print(f"Node {self.node_id} is the destination. Sending RREP to {message.originator_id}")
            self.send_rrep(message, simulation)
            return

        # Otherwise, rebroadcast the RREQ
        message.hop_count += 1
        simulation.broadcast(self, message, sender)

    def send_rrep(self, rreq_message, simulation):
        """
        Sends an RREP message back to the originator.
        """
        if self.node_id == rreq_message.dest_id:
            self.seq_num += 1

        rrep = RREPMessage(
            originator_id=rreq_message.originator_id,
            dest_id=self.node_id,
            dest_seq=self.seq_num,
            hop_count=0,
            lifetime=3000, # 3 seconds
            trust_value=1.0 # Initial trust at destination is perfect
        )

        # Find the next hop to the originator from the routing table
        next_hop_id = self.routing_table[rreq_message.originator_id].next_hop
        next_hop_node = simulation.get_node(next_hop_id)
        simulation.unicast(self, next_hop_node, rrep)

    def process_rrep(self, message, sender, simulation):
        """
        Processes a received RREP message.
        """
        print(f"Node {self.node_id} received RREP from {sender.node_id} for {message.dest_id} with trust {message.trust_value:.4f}")

        # Calculate trust of the link with the sender
        trust_history = self.trust_history.get(sender.node_id, [1.0])
        current_link_trust = self.gl_calculus.calculate_derivative(trust_history)

        # Combine trust values (average)
        new_trust = (message.trust_value * message.hop_count + current_link_trust) / (message.hop_count + 1)

        # Update route to the destination
        self.update_routing_table(message.dest_id, sender.node_id, message.hop_count + 1, message.dest_seq, new_trust)

        # If we are not the originator, forward the RREP
        if self.node_id != message.originator_id:
            message.hop_count += 1
            message.trust_value = new_trust # Update trust for forwarding
            next_hop_id = self.routing_table[message.originator_id].next_hop
            next_hop_node = simulation.get_node(next_hop_id)
            simulation.unicast(self, next_hop_node, message)
        else:
            print(f"Node {self.node_id} (originator) received final RREP. Route to {message.dest_id} established.")

    def update_routing_table(self, dest_id, next_hop_id, hop_count, seq_num, trust_value):
        """
        Updates the routing table with new information based on a combined metric.
        """
        # AODV route selection logic
        if dest_id in self.routing_table:
            entry = self.routing_table[dest_id]
            # Rule 1: Higher sequence number is always preferred
            if seq_num > entry.seq_num:
                pass # Update the route
            # Rule 2: Same sequence number, better metric
            elif seq_num == entry.seq_num:
                if self.use_gl_calculus:
                    # Our metric: lower is better (lower hop count, higher trust)
                    current_metric = entry.hop_count * (2.0 - entry.trust_value)
                    new_metric = hop_count * (2.0 - trust_value)
                    if new_metric >= current_metric:
                        return # Old route is better or same, do nothing
                else:
                    # Standard AODV: lower hop count is better
                    if hop_count >= entry.hop_count:
                        return # Old route is better or same, do nothing

        # Create or update the entry
        self.routing_table[dest_id] = RoutingTableEntry(
            destination=dest_id,
            next_hop=next_hop_id,
            hop_count=hop_count,
            seq_num=seq_num,
            lifetime=3000, # 3 seconds
            trust_value=trust_value
        )
        print(f"Node {self.node_id}: Updated route to {dest_id} via {next_hop_id} (Hops: {hop_count}, Trust: {trust_value:.4f})")


class GL_Calculus:
    def __init__(self, alpha=0.5, memory_size=10):
        self.alpha = alpha
        self.memory_size = memory_size
        self.weights = self._calculate_weights()

    def _calculate_weights(self):
        """
        Calculates the weights for the GL formula using the recursive method.
        """
        w = [1.0]
        for k in range(1, self.memory_size):
            w.append(w[-1] * (1 - (self.alpha + 1) / k))
        return w

    def calculate_derivative(self, time_series):
        """
        Calculates the GL fractional derivative for a given time series.
        """
        if not time_series:
            return 0.0

        padded_series = time_series[-self.memory_size:]
        derivative = 0.0
        for k in range(len(padded_series)):
            derivative += self.weights[k] * padded_series[len(padded_series) - 1 - k]

        return derivative

class Simulation:
    def __init__(self, num_nodes, width, height):
        self.nodes = self._create_nodes(num_nodes, width, height)
        self._find_all_neighbors()
        self.message_queue = []
        self.packets_sent = 0
        self.packets_delivered = 0
        self.routing_packets_sent = 0

    def _create_nodes(self, num_nodes, width, height):
        """
        Creates nodes with random positions.
        """
        nodes = []
        for i in range(num_nodes):
            x = random.randint(0, width)
            y = random.randint(0, height)
            nodes.append(Node(i, x, y))
        return nodes

    def _find_all_neighbors(self):
        """
        Initializes the neighbor list for each node.
        """
        for node in self.nodes:
            node.find_neighbors(self.nodes)

    def get_node(self, node_id):
        """
        Retrieves a node by its ID.
        """
        return self.nodes[node_id]

    def broadcast(self, sender, message, exclude_neighbor=None):
        """
        Broadcasts a message from a sender to its neighbors.
        """
        # print(f"Node {sender.node_id} broadcasting message.")
        if message.type == RREQ or message.type == RREP:
            self.routing_packets_sent += len(sender.neighbors)
        for neighbor in sender.neighbors:
            if neighbor != exclude_neighbor:
                self.message_queue.append((neighbor, message, sender))

    def unicast(self, sender, receiver, message):
        """
        Sends a message from a sender to a single receiver.
        """
        # print(f"Node {sender.node_id} unicasting message to {receiver.node_id}")
        if message.type == RREQ or message.type == RREP:
            self.routing_packets_sent += 1
        self.message_queue.append((receiver, message, sender))

    def run_simulation_step(self):
        """
        Processes one step of the simulation.
        """
        if not self.message_queue:
            return False

        receiver, message, sender = self.message_queue.pop(0)
        receiver.receive_message(message, sender, self)
        return True

if __name__ == "__main__":
    # Create a simple simulation
    sim = Simulation(num_nodes=5, width=150, height=150)
    print("\n--- Network Setup ---")
    for node in sim.nodes:
        print(f"Node {node.node_id} neighbors: {[n.node_id for n in node.neighbors]}")

    # --- Run Evaluation ---
    def run_evaluation(use_gl, num_packets=20):
        sim = Simulation(num_nodes=15, width=400, height=400)

        for node in sim.nodes:
            node.use_gl_calculus = use_gl

        # Setup trust history (same for both runs for fair comparison)
        random.seed(42) # Use a fixed seed
        for node in sim.nodes:
            for neighbor in node.neighbors:
                history = [random.choice([0, 1, 1, 1, 1]) for _ in range(10)]
                node.trust_history[neighbor.node_id] = history

        # Find a route from Node 0 to a non-neighbor node
        start_node = sim.get_node(0)
        end_node_id = random.randint(1, 14)
        while end_node_id in [n.node_id for n in start_node.neighbors] or end_node_id == 0:
            end_node_id = random.randint(1, 14)

        print(f"Finding route from {start_node.node_id} to {end_node_id}")
        start_node.initiate_route_discovery(end_node_id, sim)
        while sim.run_simulation_step():
            pass


        # Send data packets
        if end_node_id in start_node.routing_table:
            start_node.send_data(end_node_id, num_packets, sim)
            while sim.run_simulation_step():
                pass
        else:
            print("No route found, cannot send data.")

        # Print results
        pdr = (sim.packets_delivered / sim.packets_sent) * 100 if sim.packets_sent > 0 else 0
        print(f"\n--- Evaluation Results (GL Enabled: {use_gl}) ---")
        print(f"Packets Sent: {sim.packets_sent}")
        print(f"Packets Delivered: {sim.packets_delivered}")
        print(f"Packet Delivery Ratio (PDR): {pdr:.2f}%")
        print(f"Routing Overhead: {sim.routing_packets_sent} packets")

    run_evaluation(use_gl=False)
    run_evaluation(use_gl=True)
