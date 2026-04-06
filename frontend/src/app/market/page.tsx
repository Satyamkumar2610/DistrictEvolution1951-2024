import React from 'react';
import AppLayout from '../components/AppLayout';
import MarketDashboard from '../components/market/MarketDashboard';

export const metadata = {
    title: 'Market Economics | I-ASCAP',
    description: 'Live Mandi prices and official MSP benchmarking',
};

export default function MarketPage() {
    return (
        <AppLayout>
            <MarketDashboard />
        </AppLayout>
    );
}
