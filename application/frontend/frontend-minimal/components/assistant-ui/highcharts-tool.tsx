import Highcharts from 'highcharts';
import HighchartsReact from 'highcharts-react-official';
import { makeAssistantToolUI } from "@assistant-ui/react";

// Define the expected types for args and results
interface PlotArgs {
  title: string;
  data: number[];
  categories: string[];
}

export const HighchartsToolUI = makeAssistantToolUI<PlotArgs, any>({
  toolName: "generate_plot", // Must match your Python @tool name
  render: ({ args, result, status }) => {
    // If the tool is still running, you might want to show a loading state
    if (status.type === "running") {
      return <div className="p-4 animate-pulse bg-slate-100 rounded-lg">Generating chart...</div>;
    }

    // Use result data if available, otherwise fallback to args
    const chartData = result || args;

    const options: Highcharts.Options = {
      title: { text: chartData.title || "Data Visualization" },
      xAxis: { categories: chartData.categories },
      series: [{
        type: 'line',
        data: chartData.data
      }]
    };

    return (
      <div className="my-4 rounded-lg border bg-white p-4 shadow-sm">
        <HighchartsReact highcharts={Highcharts} options={options} />
      </div>
    );
  },
});