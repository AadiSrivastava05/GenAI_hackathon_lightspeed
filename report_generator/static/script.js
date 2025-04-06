let chartInstances = [];

async function generateReport() {
    const textarea = document.getElementById("updates");
    const updates = textarea.value.trim().split("\n").filter(line => line.trim() !== "");

    const response = await fetch('/generate_report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates })
    });

    const data = await response.json();
    if (data.error) {
        alert("Error: " + data.error);
        return;
    }

    document.getElementById("summary").innerText = data.summary;

    // Clear old charts
    const container = document.getElementById("chartsContainer");
    container.innerHTML = "<h2>Visual Reports</h2>";
    chartInstances.forEach(c => c.destroy());
    chartInstances = [];

    if (!data.charts || !data.charts.length) {
        container.innerHTML += "<p>No visualizations available.</p>";
        return;
    }
    
    data.charts.forEach((chart, index) => {
        const canvasId = `chart${index}`;
        const section = document.createElement("div");
        section.innerHTML = `<h3>${chart.title}</h3><canvas id="${canvasId}"></canvas>`;
        container.appendChild(section);

        const ctx = document.getElementById(canvasId).getContext("2d");
        const chartInstance = new Chart(ctx, {
            type: chart.type,  // could be 'line', 'bar', or 'pie'
            data: {
                labels: chart.labels,
                datasets: [{
                    label: chart.title,
                    data: chart.data,
                    backgroundColor: chart.type === 'pie' ? [
                        '#4e79a7', '#f28e2b', '#e15759', '#76b7b2',
                        '#59a14f', '#edc949', '#af7aa1', '#ff9da7'
                    ] : '#4e79a7',
                    borderColor: '#333',
                    fill: chart.type === 'line' ? false : true,
                    tension: chart.type === 'line' ? 0.3 : undefined,
                    pointRadius: chart.type === 'line' ? 5 : undefined
                }]
            }
        });
        

        chartInstances.push(chartInstance);
    });
}
