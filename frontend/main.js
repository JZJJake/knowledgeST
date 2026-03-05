document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('graph-container');
    const infoPanel = document.getElementById('info-panel');
    const infoTitle = document.getElementById('info-title');
    const infoContent = document.getElementById('info-content');
    const loading = document.getElementById('loading');

    // API Base URL (Assuming FastAPI runs on 8000)
    const API_BASE = 'http://localhost:8000/api';

    let isMagnifyingMode = false;
    let hoveredNode = null;

    document.getElementById('magnifier-toggle').addEventListener('change', (e) => {
        isMagnifyingMode = e.target.checked;
        Graph.nodeThreeObject(Graph.nodeThreeObject()); // Trigger re-render
    });

    // Initialize 3D Force Graph
    const Graph = ForceGraph3D()(container)
        .backgroundColor('#000011')
        .nodeLabel('name')
        .nodeAutoColorBy('group')
        .nodeVal('val')
        .linkWidth(link => link.type === 'explicit' ? 2 : 1)
        .linkOpacity(link => link.type === 'explicit' ? 0.8 : 0.3)
        .linkColor(link => link.type === 'explicit' ? '#aaaaaa' : '#00aaff')
        .nodeThreeObject(node => {
            // Add Sprite Text for labels
            const sprite = new SpriteText(node.name);
            sprite.color = node.color || (node.group === 'paper' ? '#ffaa00' : '#00aaff');

            // Magnifying glass effect logic
            if (isMagnifyingMode) {
                if (hoveredNode) {
                    // Check if node is the hovered node or a direct neighbor
                    const isHovered = node.id === hoveredNode.id;
                    let isNeighbor = false;

                    const links = Graph.graphData().links;
                    for (let l of links) {
                        const sourceId = typeof l.source === 'object' ? l.source.id : l.source;
                        const targetId = typeof l.target === 'object' ? l.target.id : l.target;

                        if ((sourceId === hoveredNode.id && targetId === node.id) ||
                            (targetId === hoveredNode.id && sourceId === node.id)) {
                            isNeighbor = true;
                            break;
                        }
                    }

                    if (isHovered) {
                        sprite.textHeight = 12; // Magnify hovered
                    } else if (isNeighbor) {
                        sprite.textHeight = 8;  // Partially magnify neighbors
                    } else {
                        sprite.textHeight = 2;  // Shrink others
                    }
                } else {
                    sprite.textHeight = 4; // Default size
                }
            } else {
                sprite.textHeight = 4; // Default size
            }

            return sprite;
        })
        .onNodeHover(node => {
            if (isMagnifyingMode) {
                hoveredNode = node;
                // Trigger re-render to apply magnifying effect
                Graph.nodeThreeObject(Graph.nodeThreeObject());
            }
        })
        .onNodeClick(node => {
            // Update info panel on click
            showNodeInfo(node);

            // Aim at node
            const distance = 40;
            const distRatio = 1 + distance/Math.hypot(node.x, node.y, node.z);

            const newPos = node.x || node.y || node.z
                ? { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio }
                : { x: 0, y: 0, z: distance }; // special case if node is at (0,0,0)

            Graph.cameraPosition(
                newPos, // new position
                node, // lookAt ({ x, y, z })
                3000  // ms transition duration
            );
        })
        .onNodeDragEnd(node => {
            // Fix node position after dragging (Left-click & drag)
            node.fx = node.x;
            node.fy = node.y;
            node.fz = node.z;
        });

    // 3D Physics Engine Parameter Tuning
    // Adjust gravity, repulsion, and damping for dynamic but stable effect
    Graph.d3Force('charge').strength(-150); // Stronger repulsion to prevent overlap
    Graph.d3Force('link').distance(60);     // Longer links
    Graph.d3VelocityDecay(0.2);             // Adjust damping/friction

    // Search and Render Functionality
    document.getElementById('search-btn').addEventListener('click', async () => {
        const term = document.getElementById('term-input').value.trim();
        if (!term) return;

        const statusEl = document.getElementById('status');
        statusEl.innerText = 'Initializing...';
        loading.style.display = 'block';

        try {
            // POST request to trigger DeepSeek expansion, Fetch, and Vectorization
            const processRes = await fetch(`${API_BASE}/query`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ term })
            });
            const processData = await processRes.json();

            if (processRes.ok) {
                statusEl.innerText = 'Data fetched, building graph...';

                // Fetch graph JSON topology
                const graphRes = await fetch(`${API_BASE}/graph/${processData.query_id}`);
                const graphData = await graphRes.json();

                if (graphRes.ok) {
                    // Update graph data
                    Graph.graphData(graphData);
                    statusEl.innerText = `Graph loaded: ${graphData.nodes.length} nodes.`;
                } else {
                    statusEl.innerText = `Error building graph: ${graphData.detail}`;
                }
            } else {
                statusEl.innerText = `Error: ${processData.detail}`;
            }
        } catch (e) {
            statusEl.innerText = `Network Error: ${e.message}`;
        } finally {
            loading.style.display = 'none';
        }
    });

    function escapeHtml(unsafe) {
        if (!unsafe) return '';
        return String(unsafe)
             .replace(/&/g, "&amp;")
             .replace(/</g, "&lt;")
             .replace(/>/g, "&gt;")
             .replace(/"/g, "&quot;")
             .replace(/'/g, "&#039;");
    }

    function showNodeInfo(node) {
        infoTitle.innerText = node.name;

        if (node.group === 'paper' && node.details) {
            let html = `
                <p><strong>Year:</strong> ${escapeHtml(node.details.year) || 'N/A'}</p>
                <p><strong>Source:</strong> ${escapeHtml(node.details.source)}</p>
                <p><strong>URL:</strong> <a href="${escapeHtml(node.details.url)}" target="_blank" style="color:#0af;">${escapeHtml(node.details.url)}</a></p>
                <p><strong>Authors:</strong> ${escapeHtml((node.details.authors || []).join(', '))}</p>
                <p><strong>Abstract:</strong> ${escapeHtml(node.details.abstract)}</p>
            `;
            infoContent.innerHTML = html;
        } else {
            infoContent.innerHTML = `<p>Type: Concept / Extracted Term</p>`;
        }

        infoPanel.style.display = 'block';
    }
});
