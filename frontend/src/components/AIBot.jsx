// src/components/AIBot.js
import React, { useState, useEffect } from 'react';
import './AIBot.css';

const AIBot = () => {
    const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

    useEffect(() => {
        const handleMouseMove = (e) => {
            // Calculate cursor position relative to the center of the screen
            const { innerWidth: width, innerHeight: height } = window;
            const x = (e.clientX - width / 2) / (width / 2);
            const y = (e.clientY - height / 2) / (height / 2);

            setMousePos({ x, y });
        };

        window.addEventListener('mousemove', handleMouseMove);
        return () => window.removeEventListener('mousemove', handleMouseMove);
    }, []);

    // Calculate eye translation (subtle movement)
    const eyeTransform = {
        transform: `translate(${mousePos.x * 12}px, ${mousePos.y * 10}px)`
    };

    return (
        <div className="bot-container">
            <div className="bot-shadow"></div>
            <div className="bot-orb">
                <div className="bot-eyes" style={eyeTransform}>
                    <div className="bot-eye left"></div>
                    <div className="bot-eye right"></div>
                </div>
            </div>
        </div>
    );
};

export default AIBot;
