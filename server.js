const express = require('express');
const axios = require('axios');
const cors = require('cors');
const session = require('express-session');
const path = require('path');
const xml2js = require('xml2js');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.static(path.join(__dirname, 'public')));
app.use(session({ secret: 'fantasy-mamba-secret', resave: false, saveUninitialized: true }));

const CLIENT_ID = process.env.YAHOO_CLIENT_ID;
const CLIENT_SECRET = process.env.YAHOO_CLIENT_SECRET;
const REDIRECT_URI = process.env.REDIRECT_URI;

// 1. Redirect to Yahoo Login
app.get('/auth/yahoo', (req, res) => {
    const authUrl = `https://api.login.yahoo.com/oauth2/request_auth?client_id=${CLIENT_ID}&redirect_uri=${REDIRECT_URI}&response_type=code&language=en-us`;
    res.redirect(authUrl);
});

// 2. Handle Yahoo Callback & Get Token
app.get('/callback', async (req, res) => {
    const { code } = req.query;
    try {
        const tokenResponse = await axios.post('https://api.login.yahoo.com/oauth2/get_token', 
            new URLSearchParams({
                client_id: CLIENT_ID,
                client_secret: CLIENT_SECRET,
                redirect_uri: REDIRECT_URI,
                code: code,
                grant_type: 'authorization_code'
            }).toString(), 
            { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
        );
        req.session.accessToken = tokenResponse.data.access_token;
        res.redirect('/?sync=success');
    } catch (error) {
        res.send('Authentication Failed. Check your Client ID and Secret.');
    }
});

// 3. Fetch ACTUAL Yahoo Fantasy Data
app.get('/api/data', async (req, res) => {
    if (!req.session.accessToken) return res.status(401).json({ error: 'Not authenticated' });
    try {
        // Fetch user's games and leagues
        const response = await axios.get('https://fantasysports.yahooapis.com/fantasy/v2/users;use_login=1/games;game_keys=nba/leagues', {
            headers: { Authorization: `Bearer ${req.session.accessToken}` }
        });
        
        // Convert Yahoo's XML to JSON
        const parser = new xml2js.Parser({ explicitArray: false });
        const result = await parser.parseStringPromise(response.data);
        
        // Send actual data back to the frontend
        res.json(result.fantasy_content.users.user.games.game.leagues.league);
    } catch (error) {
        res.status(500).json({ error: 'Failed to fetch Yahoo data' });
    }
});

app.listen(PORT, () => console.log(`Server running on port ${PORT}`));
