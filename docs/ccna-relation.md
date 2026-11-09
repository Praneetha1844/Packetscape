# Relation to CCNA topics

The project is a way to see, in code, several ideas from the CCNA curriculum (Enterprise Networking, Security and Automation). It is a learning aid, not a lab for Cisco devices or configuration.

| CCNA topic | Where it appears in Packetscape |
|---|---|
| Bandwidth, latency, serialization vs propagation delay | `Link`: transmit time is `size / bandwidth`, propagation is a separate delay |
| Queueing and congestion | `DropTailQueue` and `RedQueue` in `queues.py`; queue overflow drops |
| QoS concepts (tail drop, early drop) | Drop-tail compared with RED in `examples/red_vs_droptail.yaml` |
| TCP behaviour (windowing, retransmission) | `TcpSender`, `TcpReceiver` and `congestion.py` |
| TCP vs UDP traffic | TCP-like flows and CBR/Poisson flows in the same scenario |
| Network topology and path selection | `Topology.shortest_path`: hop-count routing with deterministic tie-breaking |
| Loss and error handling | Random link loss, timeouts and fast retransmit |
| Network automation | Scenarios are declarative YAML validated before running; the CLI is scriptable |

Not covered: Layer 2 switching, VLANs, IP addressing, routing protocols (OSPF, EIGRP, BGP), access control lists, NAT and device configuration. Packetscape does not simulate any of these.
