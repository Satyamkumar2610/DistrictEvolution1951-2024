import React from "react";
import ReconstructorDashboard from "../components/lineage-reconstructor/ReconstructorDashboard";

export default function ReconstructorPage() {
    return (
        <div className="p-4 lg:p-6 h-[calc(100vh-64px)] overflow-hidden">
            <ReconstructorDashboard />
        </div>
    );
}
