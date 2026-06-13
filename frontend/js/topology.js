const canvas = document.getElementById('topology-canvas');
const ctx = canvas.getContext('2d');

let lastState = null;
let animationTime = 0;

function resize() {
    const container = document.getElementById('topology-canvas-container');
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
}
window.addEventListener('resize', resize);
resize();

const COLORS = {
    "Green": "#22C55E",
    "Yellow": "#F59E0B",
    "Red": "#EF4444",
    "Purple": "#8B5CF6",
    "Converter": "#38BDF8"
};

function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    animationTime += 0.05;

    if (!lastState || !lastState.topology) {
        requestAnimationFrame(draw);
        return;
    }

    const nodes = lastState.topology.nodes;
    const eastNodes = nodes.filter(n => n.region === 'east');
    const westNodes = nodes.filter(n => n.region === 'west');

    const centerY = canvas.height / 2;
    const centerX = canvas.width / 2;

    // Draw Converter (Center)
    ctx.fillStyle = COLORS["Converter"];
    ctx.beginPath();
    ctx.roundRect(centerX - 30, centerY - 40, 60, 80, 8);
    ctx.fill();
    ctx.fillStyle = "#fff";
    ctx.font = "10px Inter";
    ctx.textAlign = "center";
    ctx.fillText("HVDC", centerX, centerY);

    const util = lastState.topology.converter.utilization || 0;
    const flow = lastState.topology.converter.flow_mw || 0;
    ctx.fillText(`${Math.abs(flow).toFixed(0)} MW`, centerX, centerY + 15);

    // Glow converter if utilizing
    if (util > 0.1) {
        ctx.shadowBlur = util * 20;
        ctx.shadowColor = COLORS["Converter"];
        ctx.beginPath();
        ctx.roundRect(centerX - 30, centerY - 40, 60, 80, 8);
        ctx.stroke();
        ctx.shadowBlur = 0;
    }

    // Node plotting helper
    function drawNodes(nodeList, offsetX, isEast) {
        const spacing = canvas.height / (nodeList.length + 1);
        nodeList.forEach((node, i) => {
            const x = offsetX;
            const y = (i + 1) * spacing;

            // Draw connection line
            ctx.beginPath();
            ctx.moveTo(x, y);
            ctx.lineTo(centerX + (isEast ? -30 : 30), centerY);
            ctx.strokeStyle = "rgba(255, 255, 255, 0.2)";
            ctx.lineWidth = 2;
            ctx.stroke();

            // Animate flow if utilizing
            if (util > 0) {
                // East to West flow (flow > 0 means E->W)
                const flowDir = isEast ? (flow > 0 ? 1 : -1) : (flow > 0 ? -1 : 1);
                if (flowDir === 1) { // Power leaving node
                    const dashOffset = -animationTime * 20;
                    ctx.beginPath();
                    ctx.moveTo(x, y);
                    ctx.lineTo(centerX + (isEast ? -30 : 30), centerY);
                    ctx.setLineDash([10, 15]);
                    ctx.lineDashOffset = dashOffset;
                    ctx.strokeStyle = COLORS["Converter"];
                    ctx.stroke();
                    ctx.setLineDash([]);
                }
            }

            // Draw Node
            const color = COLORS[node.status] || COLORS["Green"];
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(x, y, 15, 0, Math.PI * 2);
            ctx.fill();

            // Node Label
            ctx.fillStyle = "#E5E7EB";
            ctx.font = "12px JetBrains Mono";
            ctx.textAlign = isEast ? "right" : "left";
            ctx.fillText(node.id, x + (isEast ? -25 : 25), y + 4);

            // Stats
            ctx.fillStyle = "#9CA3AF";
            ctx.font = "10px Inter";
            ctx.fillText(`Gen: ${node.generation_mw.toFixed(0)}`, x + (isEast ? -25 : 25), y + 18);
            ctx.fillText(`Dem: ${node.demand_mw.toFixed(0)}`, x + (isEast ? -25 : 25), y + 30);
        });
    }

    // East Nodes (Left)
    drawNodes(eastNodes, 100, true);

    // West Nodes (Right)
    drawNodes(westNodes, canvas.width - 100, false);

    requestAnimationFrame(draw);
}

simStream.subscribe((state) => {
    lastState = state;
});

draw();
