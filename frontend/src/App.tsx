import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import HomePage from './pages/HomePage';
import SchemaPage from './pages/SchemaPage';
import PreviewPage from './pages/PreviewPage';

const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="schema" element={<SchemaPage />} />
          <Route path="preview" element={<PreviewPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;
