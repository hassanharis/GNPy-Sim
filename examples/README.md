# Example Data Files

This directory contains example configuration files for the GNPy Simulator.

## Files

### simple_topology.json
A basic 3-node linear topology with:
- 3 ROADM sites (Site A, B, C)
- 2 inline amplifiers (ILAs)
- 80 km fiber spans
- Transceivers at endpoints

**Use case:** Quick testing and learning the interface

### simple_equipment.json
Equipment library containing:
- 3 EDFA types (low, medium, high gain)
- 2 fiber types (SSMF, LEAF)
- ROADM specifications
- 2 transceiver types (100G, 200G)
- Default spectral information

**Use case:** Standard equipment for most simulations

### simple_services.json
Service request file with:
- Single path request from Site A to Site C
- 200G capacity requirement
- DP-16QAM modulation format

**Use case:** Automated path computation

## How to Use

1. **In the Application:**
   - Navigate to appropriate section
   - Use the file uploader
   - Select these files from the `examples` folder

2. **Quick Test Workflow:**
   ```
   Step 1: Upload simple_equipment.json (Section 1)
   Step 2: Upload simple_topology.json (Section 3)
   Step 3: Upload simple_services.json (Section 5)
          OR
   Step 3: Manually select nodes (Section 6)
   ```

3. **Expected Results:**
   - Path length: ~320 km
   - GSNR: 18-22 dB (typical)
   - OSNR: 18-22 dB (typical)
   - Feasibility: Should be feasible for 200G

## Creating Your Own Files

### Topology File Structure
```json
{
  "elements": [
    {"uid": "node_name", "type": "ROADM/ILA/Transceiver"},
    {"type": "Fiber", "from": "node1", "to": "node2", "length": 80.0}
  ]
}
```

### Service File Structure
```json
{
  "path-request": [
    {
      "request-id": "req_1",
      "source": "source_node",
      "destination": "dest_node"
    }
  ]
}
```

## Tips

- Start with these simple examples
- Modify node names and lengths to match your network
- Copy and adapt for your specific needs
- Validate JSON syntax before uploading

## More Examples

For more complex examples, visit:
https://github.com/Telecominfraproject/oopt-gnpy/tree/master/gnpy/example-data
