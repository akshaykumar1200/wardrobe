import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Navbar from './components/Navbar';
import Closet from './pages/Closet';
import Upload from './pages/Upload';
import Review from './pages/Review';
import Login from './pages/Login';
import Signup from './pages/Signup';
import Admin from './pages/Admin';
import ChangePassword from './pages/ChangePassword';
import ForgotPassword from './pages/ForgotPassword';
import ResetPassword from './pages/ResetPassword';
import { api } from './api';

export default function App() {
  const [user, setUser] = useState(null);
  const [checkingAuth, setCheckingAuth] = useState(true);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const currentUser = await api('/api/auth/me');
        setUser(currentUser);
      } catch (err) {
        setUser(null);
      } finally {
        setCheckingAuth(false);
      }
    };
    checkAuth();
  }, []);

  if (checkingAuth) {
    return (
      <div className="min-h-screen bg-paper flex items-center justify-center text-ink-muted text-sm font-medium">
        Loading...
      </div>
    );
  }

  return (
    <Router>
      <div className="min-h-screen bg-paper flex flex-col">
        <Navbar user={user} setUser={setUser} />
        <main className="flex-1">
          <Routes>
            <Route
              path="/login"
              element={user ? <Navigate to="/" replace /> : <Login setUser={setUser} />}
            />
            <Route
              path="/signup"
              element={user ? <Navigate to="/" replace /> : <Signup setUser={setUser} />}
            />
            <Route path="/forgot" element={<ForgotPassword />} />
            <Route path="/reset" element={<ResetPassword />} />

            {/* Protected User Routes */}
            <Route
              path="/"
              element={user ? <Closet /> : <Navigate to="/login" replace />}
            />
            <Route
              path="/upload"
              element={user ? <Upload /> : <Navigate to="/login" replace />}
            />
            <Route
              path="/password"
              element={user ? <ChangePassword /> : <Navigate to="/login" replace />}
            />
            <Route
              path="/review"
              element={user ? <Review /> : <Navigate to="/login" replace />}
            />

            {/* Admin Route */}
            <Route
              path="/admin"
              element={
                user && user.is_admin ? <Admin /> : <Navigate to="/" replace />
              }
            />

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}
